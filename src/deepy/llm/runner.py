from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from deepy.audit import ApprovalDecision, AuditMode, AuditModeState, AuditPolicy, PendingApproval, parse_audit_mode
from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings, load_settings
from deepy.mcp import DeepyMcpRuntime
from deepy.sessions import DeepySession
from deepy.skills import find_skill
from deepy.todos import normalize_todo_items
from deepy.tools import ToolRuntime
from deepy.usage import TokenUsage, merge_usage, normalize_usage, usage_from_run_result
from deepy.utils import launch_notify_script, log_api_error, log_debug_event

from .agent import build_deepy_agent
from .cache_context import (
    build_cache_prefix_snapshot,
    reset_current_cache_prefix_snapshot,
    set_current_cache_prefix_snapshot,
)
from .compaction import ContextCompactionError, ensure_context_ready
from .context import build_session_input_callback
from .events import DeepyStreamEvent, normalize_stream_event
from .multimodal import (
    PromptImageAttachment,
    build_user_input,
    supports_image_input,
)
from .provider import ProviderBundle, build_provider_bundle
from .runner_approvals import _approval_decisions
from .runner_errors import _api_status_error_response, format_deepseek_api_error
from .runner_interrupt import (
    _cancel_stream_result,
    _finish_interrupt_task,
    _pending_questions_from_tool_output,
    _reconcile_interrupted_session_tail,
    _watch_stream_interrupt,
)

DEFAULT_MAX_TURNS = 100

__all__ = ["DEFAULT_MAX_TURNS", "RunSummary", "format_deepseek_api_error", "run_prompt_once"]


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
    audit_mode: AuditMode | str | AuditModeState | None = None,
    approval_resolver: Callable[
        [list[PendingApproval]],
        list[ApprovalDecision] | Awaitable[list[ApprovalDecision]],
    ]
    | None = None,
    image_attachments: list[PromptImageAttachment] | None = None,
) -> RunSummary:
    from agents import RunConfig, Runner
    from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError
    from openai import APIStatusError

    root = (project_root or Path.cwd()).resolve()
    resolved_settings = settings or load_settings()
    resolved_provider = provider or build_provider_bundle(resolved_settings)
    audit_state = audit_mode if isinstance(audit_mode, AuditModeState) else AuditModeState(
        parse_audit_mode(audit_mode, default=resolved_settings.audit.mode)
    )
    audit_policy = AuditPolicy(lambda: audit_state.mode, resolved_settings.audit)
    session = DeepySession.open(root, session_id) if session_id else DeepySession.create(root)
    effective_image_attachments = (
        list(image_attachments or []) if supports_image_input(resolved_settings) else []
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
        created_mcp_runtime = DeepyMcpRuntime(
            resolved_settings,
            project_root=root,
            audit_policy=audit_policy,
        )
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
        audit_policy=audit_policy,
    )
    prefix_snapshot = build_cache_prefix_snapshot(
        resolved_settings,
        system_instructions=str(getattr(agent, "instructions", "") or ""),
        tools=list(getattr(agent, "tools", []) or []),
        mcp_servers=list(getattr(agent, "mcp_servers", []) or []),
        model_settings=resolved_provider.model_settings,
        skill_names=[str(getattr(skill, "name", "")) for skill in loaded_skills],
        runtime_context_key=str(root),
    )
    session.record_cache_prefix_snapshot(prefix_snapshot)
    started_at = time.time()
    try:
        readiness = await ensure_context_ready(
            session,
            resolved_settings,
            provider=resolved_provider,
            prefix_snapshot=prefix_snapshot,
            prefix_tools=list(getattr(agent, "tools", []) or []),
            prefix_mcp_servers=list(getattr(agent, "mcp_servers", []) or []),
            additional_input=build_user_input(prompt, effective_image_attachments),
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
    prefix_token: Any | None = None
    try:
        prefix_token = set_current_cache_prefix_snapshot(prefix_snapshot)
        run_input: Any = build_user_input(prompt, effective_image_attachments)
        while True:
            result = Runner.run_streamed(
                agent,
                input=run_input,
                max_turns=max_turns,
                run_config=run_config,
                session=session,  # ty: ignore[invalid-argument-type] - DeepySession matches the SDK Session protocol at runtime.
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
            interrupted = interrupted or await _finish_interrupt_task(interrupt_task)
            interrupt_task = None
            if interrupted or waiting_for_user:
                break
            interruptions = list(getattr(result, "interruptions", []) or [])
            if not interruptions:
                break
            state = result.to_state()
            decisions = await _approval_decisions(
                interruptions,
                approval_resolver=approval_resolver,
                runtime=runtime,
            )
            for interruption, decision in zip(interruptions, decisions, strict=False):
                if decision.outcome == "approve":
                    state.approve(interruption, always_approve=decision.always)
                else:
                    state.reject(
                        interruption,
                        always_reject=decision.always,
                        rejection_message=decision.rejection_message
                        or "Tool execution was rejected by the user audit approval decision.",
                    )
            run_input = state
        if prefix_token is not None:
            reset_current_cache_prefix_snapshot(prefix_token)
            prefix_token = None
    except MaxTurnsExceeded:
        if prefix_token is not None:
            reset_current_cache_prefix_snapshot(prefix_token)
            prefix_token = None
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
        if prefix_token is not None:
            reset_current_cache_prefix_snapshot(prefix_token)
            prefix_token = None
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
        if prefix_token is not None:
            reset_current_cache_prefix_snapshot(prefix_token)
            prefix_token = None
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
        if prefix_token is not None:
            reset_current_cache_prefix_snapshot(prefix_token)
            prefix_token = None
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


def _run_status(*, interrupted: bool, waiting_for_user: bool, complete: bool) -> str:
    if interrupted:
        return "interrupted"
    if waiting_for_user:
        return "waiting_for_user"
    return "completed" if complete else "incomplete"
