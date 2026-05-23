from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from deepy.config import Settings, load_settings
from deepy.sessions.jsonl import DeepyJsonlSession
from deepy.skills import find_skill
from deepy.mcp import DeepyMcpRuntime
from deepy.todos import normalize_todo_items
from deepy.background_tasks import BackgroundTaskManager
from deepy.tools import ToolRuntime
from deepy.usage import TokenUsage, merge_usage, normalize_usage, usage_from_run_result
from deepy.utils import json as json_utils
from deepy.utils import launch_notify_script, log_api_error, log_debug_event

from .agent import build_deepy_agent
from .compaction import ContextCompactionError, ensure_context_ready
from .context import build_session_input_callback
from .events import DeepyStreamEvent, normalize_stream_event
from .provider import ProviderBundle, build_provider_bundle

DEFAULT_MAX_TURNS = 100
INTERRUPTED_MARKER_TEXT = (
    "Interrupted by user with Esc. This turn was stopped before completion. "
    "Do not continue the interrupted request unless the user explicitly asks to continue."
)
INTERRUPTED_TOOL_OUTPUT_TEXT = "Tool execution interrupted by user with Esc."


@dataclass(frozen=True)
class RunSummary:
    output: str
    session_id: str
    complete: bool
    interrupted: bool = False
    status: str = "completed"
    pending_questions: list[dict[str, Any]] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    duration_ms: int = 0


async def run_prompt_once(
    prompt: str,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
    provider: ProviderBundle | None = None,
    emit: Callable[[str], None] | None = None,
    emit_event: Callable[[DeepyStreamEvent], None] | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    session_id: str | None = None,
    skill_names: list[str] | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
    background_tasks: BackgroundTaskManager | None = None,
    should_interrupt: Callable[[], bool] | None = None,
    cancel_mode: Literal["immediate", "after_turn"] = "immediate",
) -> RunSummary:
    from agents import RunConfig, Runner
    from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError
    from openai import APIStatusError

    root = (project_root or Path.cwd()).resolve()
    resolved_settings = settings or load_settings()
    resolved_provider = provider or build_provider_bundle(resolved_settings)
    session = (
        DeepyJsonlSession.open(root, session_id) if session_id else DeepyJsonlSession.create(root)
    )
    initial_todos, _ = normalize_todo_items(session.todo_state())
    runtime = ToolRuntime(
        cwd=root,
        settings=resolved_settings,
        background_tasks=background_tasks or BackgroundTaskManager(),
        should_interrupt=should_interrupt,
        todo_items=initial_todos or [],
    )
    created_mcp_runtime: DeepyMcpRuntime | None = None
    if mcp_runtime is None:
        created_mcp_runtime = DeepyMcpRuntime(resolved_settings, project_root=root)
        mcp_runtime = created_mcp_runtime
        await mcp_runtime.connect()
    loaded_skills = _resolve_loaded_skills(root, prompt, skill_names)
    agent = build_deepy_agent(
        resolved_settings,
        runtime,
        project_root=root,
        provider=resolved_provider,
        loaded_skills=loaded_skills,
        mcp_servers=mcp_runtime.active_servers,
        preferred_mcp_web_search_tools=mcp_runtime.preferred_web_search_tools,
        emit_event=emit_event,
    )
    started_at = time.time()
    try:
        readiness = await ensure_context_ready(
            session,
            resolved_settings,
            provider=resolved_provider,
            additional_input=prompt,
        )
    except ContextCompactionError as exc:
        duration_ms = int((time.time() - started_at) * 1000) if "started_at" in locals() else 0
        await _cleanup_created_mcp(created_mcp_runtime)
        return RunSummary(
            output=f"Context compaction failed: {exc}",
            session_id=session.session_id,
            complete=False,
            status="context_compaction_failed",
            duration_ms=duration_ms,
        )
    if readiness.compacted and emit_event is not None:
        compaction = readiness.compaction
        detail = (
            f"Auto-compacted context {readiness.before_tokens:,} -> {readiness.after_tokens:,} tokens"
            if compaction is None
            else (
                f"Auto-compacted context {compaction.before_tokens:,} -> "
                f"{compaction.after_tokens:,} tokens"
            )
        )
        emit_event(DeepyStreamEvent(kind="status", text=detail))
    run_config = RunConfig(
        workflow_name="Deepy",
        trace_include_sensitive_data=False,
        reasoning_item_id_policy="omit",
        session_input_callback=build_session_input_callback(resolved_settings),
    )

    chunks: list[str] = []
    result: Any | None = None
    interrupted = False
    waiting_for_user = False
    pending_questions: list[dict[str, Any]] = []
    usage = TokenUsage()
    interrupt_task: asyncio.Task[bool] | None = None
    session_baseline_count = len(await session.get_items())
    try:
        result = Runner.run_streamed(
            agent,
            input=prompt,
            max_turns=max_turns,
            run_config=run_config,
            session=session,  # ty: ignore[invalid-argument-type] - DeepyJsonlSession matches the SDK Session protocol at runtime.
        )
        if should_interrupt is not None:
            interrupt_task = asyncio.create_task(
                _watch_stream_interrupt(
                    result,
                    should_interrupt=should_interrupt,
                    cancel_mode=cancel_mode,
                )
            )
        async for event in result.stream_events():
            if should_interrupt is not None and should_interrupt():
                _cancel_stream_result(result, mode=cancel_mode)
                interrupted = True
                break
            normalized = normalize_stream_event(event)
            if normalized is None:
                continue
            if normalized.kind == "usage":
                usage = merge_usage(usage, normalize_usage(normalized.payload.get("usage")))
            if emit_event is not None:
                emit_event(normalized)
            if normalized.kind == "tool_output":
                questions = _pending_questions_from_tool_output(normalized.text)
                if questions:
                    pending_questions = questions
                    waiting_for_user = True
                    _cancel_stream_result(result, mode="after_turn")
                    break
            if normalized.kind != "text_delta" or not normalized.text:
                continue
            chunks.append(normalized.text)
            if emit is not None:
                emit(normalized.text)
            if should_interrupt is not None and should_interrupt():
                _cancel_stream_result(result, mode=cancel_mode)
                interrupted = True
                break
    except MaxTurnsExceeded:
        interrupted = interrupted or await _finish_interrupt_task(interrupt_task)
        result_usage = usage_from_run_result(result)
        if result_usage.known:
            usage = result_usage
        duration_ms = int((time.time() - started_at) * 1000)
        session.record_usage(usage)
        await _cleanup_created_mcp(created_mcp_runtime)
        return RunSummary(
            output=_max_turns_output(chunks, max_turns=max_turns),
            session_id=session.session_id,
            complete=False,
            status="max_turns_exceeded",
            usage=usage,
            duration_ms=duration_ms,
        )
    except APIStatusError as exc:
        interrupted = interrupted or await _finish_interrupt_task(interrupt_task)
        log_api_error(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "location": "deepy.llm.runner.run_prompt_once",
                "requestId": session.session_id,
                "sessionId": session.session_id,
                "model": resolved_settings.model.name,
                "baseURL": resolved_settings.model.base_url,
                "error": exc,
                "response": _api_status_error_response(exc),
                "request": {
                    "input": prompt,
                    "max_turns": max_turns,
                },
            }
        )
        result_usage = usage_from_run_result(result)
        if result_usage.known:
            usage = result_usage
        duration_ms = int((time.time() - started_at) * 1000)
        session.record_usage(usage)
        await _cleanup_created_mcp(created_mcp_runtime)
        return RunSummary(
            output=format_deepseek_api_error(exc),
            session_id=session.session_id,
            complete=False,
            status="api_error",
            usage=usage,
            duration_ms=duration_ms,
        )
    except ModelBehaviorError as exc:
        interrupted = interrupted or await _finish_interrupt_task(interrupt_task)
        log_api_error(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "location": "deepy.llm.runner.run_prompt_once",
                "requestId": session.session_id,
                "sessionId": session.session_id,
                "model": resolved_settings.model.name,
                "baseURL": resolved_settings.model.base_url,
                "error": exc,
                "request": {
                    "input": prompt,
                    "max_turns": max_turns,
                },
            }
        )
        result_usage = usage_from_run_result(result)
        if result_usage.known:
            usage = result_usage
        duration_ms = int((time.time() - started_at) * 1000)
        session.record_usage(usage)
        await _cleanup_created_mcp(created_mcp_runtime)
        return RunSummary(
            output=f"Agent behavior error: {exc}",
            session_id=session.session_id,
            complete=False,
            status="agent_error",
            usage=usage,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        await _finish_interrupt_task(interrupt_task)
        log_api_error(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "location": "deepy.llm.runner.run_prompt_once",
                "requestId": session.session_id,
                "sessionId": session.session_id,
                "model": resolved_settings.model.name,
                "baseURL": resolved_settings.model.base_url,
                "error": exc,
                "request": {
                    "input": prompt,
                    "max_turns": max_turns,
                },
            }
        )
        await _cleanup_created_mcp(created_mcp_runtime)
        raise

    interrupted = interrupted or await _finish_interrupt_task(interrupt_task)
    if interrupted:
        await _reconcile_interrupted_session_tail(
            session,
            baseline_count=session_baseline_count,
            prompt=prompt,
        )

    final_output = getattr(result, "final_output", None)
    output = final_output if isinstance(final_output, str) else "".join(chunks)
    result_usage = usage_from_run_result(result)
    if result_usage.known:
        usage = result_usage
    session.record_usage(usage)
    duration_ms = int((time.time() - started_at) * 1000)
    if resolved_settings.logging.debug:
        log_debug_event(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "location": "deepy.llm.runner.run_prompt_once",
                "sessionId": session.session_id,
                "model": resolved_settings.model.name,
                "baseURL": resolved_settings.model.base_url,
                "durationMs": duration_ms,
                "request": {
                    "input": prompt,
                    "max_turns": max_turns,
                },
                "response": {"output": output, "usage": usage.to_dict()},
            }
        )
    if resolved_settings.notify.enabled and resolved_settings.notify.command:
        launch_notify_script(resolved_settings.notify.command, duration_ms, root)
    try:
        return RunSummary(
            output=output,
            session_id=session.session_id,
            complete=False
            if interrupted or waiting_for_user
            else bool(getattr(result, "is_complete", True)),
            interrupted=interrupted,
            status=_run_status(
                interrupted=interrupted,
                waiting_for_user=waiting_for_user,
                complete=bool(getattr(result, "is_complete", True)),
            ),
            pending_questions=pending_questions,
            usage=usage,
            duration_ms=duration_ms,
        )
    finally:
        if created_mcp_runtime is not None:
            await created_mcp_runtime.cleanup()


async def _cleanup_created_mcp(mcp_runtime: DeepyMcpRuntime | None) -> None:
    if mcp_runtime is not None:
        await mcp_runtime.cleanup()


def _resolve_loaded_skills(
    root: Path,
    prompt: str,
    skill_names: list[str] | None,
) -> list[Any]:
    if skill_names:
        loaded_skills = []
        for skill_name in skill_names:
            skill = find_skill(root, skill_name)
            if skill is None:
                raise ValueError(f"Skill not found: {skill_name}")
            loaded_skills.append(skill)
        return loaded_skills
    return []


def _max_turns_output(chunks: list[str], *, max_turns: int) -> str:
    message = (
        f"Stopped after reaching the max turn limit ({max_turns}). "
        "The session was preserved; review the tool output above and ask Deepy to continue, "
        "or narrow the request if it keeps looping."
    )
    partial = "".join(chunks).strip()
    return f"{partial}\n\n{message}" if partial else message


def format_deepseek_api_error(error: Any) -> str:
    status_code = _safe_int(getattr(error, "status_code", None))
    status = DEEPSEEK_ERROR_CODES.get(status_code) if status_code is not None else None
    title = f"DeepSeek API error {status_code}" if status_code is not None else "DeepSeek API error"
    if status is not None:
        title = f"{title}: {status.title}"

    lines = [title]
    server_message = _api_status_error_message(error)
    if server_message:
        lines.extend(["", f"Server message: {server_message}"])
    if status is not None:
        lines.extend(["", f"Reason: {status.reason}", f"Suggestion: {status.suggestion}"])

    error_code = _api_error_body_field(error, "code")
    error_type = _api_error_body_field(error, "type")
    if error_code or error_type:
        detail_parts = [
            part
            for part in (
                f"code={error_code}" if error_code else "",
                f"type={error_type}" if error_type else "",
            )
            if part
        ]
        detail = ", ".join(detail_parts)
        lines.append(f"Detail: {detail}")
    return "\n".join(lines)


@dataclass(frozen=True)
class DeepSeekErrorStatus:
    title: str
    reason: str
    suggestion: str


DEEPSEEK_ERROR_CODES: dict[int, DeepSeekErrorStatus] = {
    400: DeepSeekErrorStatus(
        title="格式错误",
        reason="请求体格式错误。",
        suggestion="请根据错误信息提示修改请求体。",
    ),
    401: DeepSeekErrorStatus(
        title="认证失败",
        reason="API key 错误，认证失败。",
        suggestion="请检查 API key 是否正确；如果还没有 API key，请先创建 API key。",
    ),
    402: DeepSeekErrorStatus(
        title="余额不足",
        reason="账号余额不足。",
        suggestion="请确认账户余额，并前往 DeepSeek 充值页面充值。",
    ),
    422: DeepSeekErrorStatus(
        title="参数错误",
        reason="请求体参数错误。",
        suggestion="请根据错误信息提示修改相关参数。",
    ),
    429: DeepSeekErrorStatus(
        title="请求速率达到上限",
        reason="请求速率（TPM 或 RPM）达到上限。",
        suggestion="请合理规划请求速率，稍后重试。",
    ),
    500: DeepSeekErrorStatus(
        title="服务器故障",
        reason="DeepSeek 服务器内部故障。",
        suggestion="请等待后重试；如果问题持续存在，请联系 DeepSeek 支持。",
    ),
    503: DeepSeekErrorStatus(
        title="服务器繁忙",
        reason="服务器负载过高。",
        suggestion="请稍后重试请求。",
    ),
}


def _api_status_error_message(error: Any) -> str:
    body_message = _api_error_body_field(error, "message")
    if body_message:
        return body_message
    message = getattr(error, "message", None)
    return str(message).strip() if message else str(error).strip()


def _api_status_error_response(error: Any) -> dict[str, Any]:
    response = getattr(error, "response", None)
    result: dict[str, Any] = {}
    status_code = _safe_int(getattr(error, "status_code", None))
    if status_code is not None:
        result["statusCode"] = status_code
    request_id = getattr(error, "request_id", None)
    if request_id:
        result["requestId"] = request_id
    body = getattr(error, "body", None)
    if body is not None:
        result["body"] = body
    if response is not None:
        url = getattr(response, "url", None)
        if url is not None:
            result["url"] = str(url)
    return result


def _api_error_body_field(error: Any, field: str) -> str:
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        body_error = body.get("error")
        if isinstance(body_error, dict):
            value = body_error.get(field)
            return str(value).strip() if value is not None else ""
        value = body.get(field)
        return str(value).strip() if value is not None else ""
    return ""


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cancel_stream_result(
    result: Any,
    *,
    mode: Literal["immediate", "after_turn"],
) -> None:
    cancel = getattr(result, "cancel", None)
    if not callable(cancel):
        return
    try:
        cancel(mode=mode)
    except TypeError:
        cancel()


async def _watch_stream_interrupt(
    result: Any,
    *,
    should_interrupt: Callable[[], bool],
    cancel_mode: Literal["immediate", "after_turn"],
) -> bool:
    while not bool(getattr(result, "is_complete", False)):
        if should_interrupt():
            _cancel_stream_result(result, mode=cancel_mode)
            return True
        await asyncio.sleep(0.05)
    return False


async def _finish_interrupt_task(task: asyncio.Task[bool] | None) -> bool:
    if task is None:
        return False
    if task.done():
        return task.result()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return False


async def _reconcile_interrupted_session_tail(
    session: DeepyJsonlSession,
    *,
    baseline_count: int,
    prompt: str,
) -> None:
    items = await session.get_items()
    if baseline_count < 0 or baseline_count > len(items):
        return
    suffix = items[baseline_count:]
    if not suffix:
        return

    if len(suffix) == 1 and _is_user_prompt_item(suffix[0], prompt):
        await session.pop_item()
        return

    additions = _interrupted_tool_output_items(suffix)
    if not _is_interrupt_marker_item(suffix[-1]):
        additions.append(_interrupted_marker_item())
    if additions:
        await session.add_items(additions)


def _is_user_prompt_item(item: dict[str, Any], prompt: str) -> bool:
    if item.get("role") != "user":
        return False
    return _item_text_content(item) == prompt


def _item_text_content(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for part in content:
        if isinstance(part, dict):
            text = part.get("text")
            if text is None:
                text = part.get("input_text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _interrupted_tool_output_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output_call_ids = {
        call_id
        for item in items
        if (call_id := _function_call_output_id(item))
    }
    additions: list[dict[str, Any]] = []
    added_call_ids: set[str] = set()
    for item in items:
        for call_id, output_item in _missing_output_items_for_call(item, output_call_ids):
            if call_id in added_call_ids:
                continue
            additions.append(output_item)
            added_call_ids.add(call_id)
    return additions


def _missing_output_items_for_call(
    item: dict[str, Any],
    output_call_ids: set[str],
) -> list[tuple[str, dict[str, Any]]]:
    call_id = _function_call_id(item)
    if call_id:
        return (
            []
            if call_id in output_call_ids
            else [
                (
                    call_id,
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": INTERRUPTED_TOOL_OUTPUT_TEXT,
                    },
                )
            ]
        )

    missing: list[tuple[str, dict[str, Any]]] = []
    if item.get("role") != "assistant":
        return missing
    tool_calls = item.get("tool_calls")
    if not isinstance(tool_calls, list):
        return missing
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        chat_call_id = tool_call.get("id")
        if not isinstance(chat_call_id, str) or not chat_call_id or chat_call_id in output_call_ids:
            continue
        missing.append(
            (
                chat_call_id,
                {
                    "role": "tool",
                    "tool_call_id": chat_call_id,
                    "content": INTERRUPTED_TOOL_OUTPUT_TEXT,
                },
            )
        )
    return missing


def _function_call_id(item: dict[str, Any]) -> str:
    if item.get("type") != "function_call":
        return ""
    call_id = item.get("call_id")
    if call_id is None:
        call_id = item.get("id")
    return call_id if isinstance(call_id, str) else ""


def _function_call_output_id(item: dict[str, Any]) -> str:
    if item.get("type") == "function_call_output":
        call_id = item.get("call_id")
        return call_id if isinstance(call_id, str) else ""
    if item.get("role") == "tool":
        tool_call_id = item.get("tool_call_id")
        return tool_call_id if isinstance(tool_call_id, str) else ""
    return ""


def _interrupted_marker_item() -> dict[str, Any]:
    return {"role": "assistant", "content": INTERRUPTED_MARKER_TEXT}


def _is_interrupt_marker_item(item: dict[str, Any]) -> bool:
    return item.get("role") == "assistant" and item.get("content") == INTERRUPTED_MARKER_TEXT


def _pending_questions_from_tool_output(output: str) -> list[dict[str, Any]]:
    if not output.strip():
        return []
    try:
        payload = json_utils.loads(output)
    except json_utils.JSONDecodeError:
        return []
    if not isinstance(payload, dict) or payload.get("awaitUserResponse") is not True:
        return []
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("kind") != "ask_user_question":
        return []
    questions = metadata.get("questions")
    if not isinstance(questions, list):
        return []
    return [question for question in questions if isinstance(question, dict)]


def _run_status(*, interrupted: bool, waiting_for_user: bool, complete: bool) -> str:
    if interrupted:
        return "interrupted"
    if waiting_for_user:
        return "waiting_for_user"
    return "completed" if complete else "incomplete"
