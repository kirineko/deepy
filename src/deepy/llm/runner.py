from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from deepy.config import Settings, load_settings
from deepy.sessions.jsonl import DeepyJsonlSession
from deepy.skills import discover_skills, find_skill, match_skills_for_prompt
from deepy.tools import ToolRuntime
from deepy.utils import launch_notify_script, log_api_error, log_debug_event

from .agent import build_deepy_agent
from .context import build_session_input_callback
from .events import DeepyStreamEvent, normalize_stream_event
from .provider import ProviderBundle, build_provider_bundle


@dataclass(frozen=True)
class RunSummary:
    output: str
    session_id: str
    complete: bool
    interrupted: bool = False
    status: str = "completed"
    pending_questions: list[dict[str, Any]] = field(default_factory=list)


async def run_prompt_once(
    prompt: str,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
    provider: ProviderBundle | None = None,
    emit: Callable[[str], None] | None = None,
    emit_event: Callable[[DeepyStreamEvent], None] | None = None,
    max_turns: int = 10,
    session_id: str | None = None,
    skill_names: list[str] | None = None,
    image_data_urls: list[str] | None = None,
    should_interrupt: Callable[[], bool] | None = None,
    cancel_mode: Literal["immediate", "after_turn"] = "immediate",
) -> RunSummary:
    from agents import RunConfig, Runner

    root = (project_root or Path.cwd()).resolve()
    resolved_settings = settings or load_settings()
    resolved_provider = provider or build_provider_bundle(resolved_settings)
    runtime = ToolRuntime(cwd=root, settings=resolved_settings)
    loaded_skills = _resolve_loaded_skills(root, prompt, skill_names)
    agent = build_deepy_agent(
        resolved_settings,
        runtime,
        project_root=root,
        provider=resolved_provider,
        loaded_skills=loaded_skills,
    )
    session = (
        DeepyJsonlSession.open(root, session_id)
        if session_id
        else DeepyJsonlSession.create(root)
    )
    run_config = RunConfig(
        workflow_name="Deepy",
        trace_include_sensitive_data=False,
        reasoning_item_id_policy="omit",
        session_input_callback=build_session_input_callback(resolved_settings),
    )

    started_at = time.time()
    chunks: list[str] = []
    result: Any | None = None
    interrupted = False
    waiting_for_user = False
    pending_questions: list[dict[str, Any]] = []
    try:
        result = Runner.run_streamed(
            agent,
            input=_build_runner_input(prompt, image_data_urls or []),
            max_turns=max_turns,
            run_config=run_config,
            session=session,
        )
        async for event in result.stream_events():
            if should_interrupt is not None and should_interrupt():
                _cancel_stream_result(result, mode=cancel_mode)
                interrupted = True
                break
            normalized = normalize_stream_event(event)
            if normalized is None:
                continue
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
    except Exception as exc:
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
                    "image_count": len(image_data_urls or []),
                },
            }
        )
        raise

    final_output = getattr(result, "final_output", None)
    output = final_output if isinstance(final_output, str) else "".join(chunks)
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
                    "image_count": len(image_data_urls or []),
                },
                "response": {"output": output},
            }
        )
    if resolved_settings.notify.enabled and resolved_settings.notify.command:
        launch_notify_script(resolved_settings.notify.command, duration_ms, root)
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
    )


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
    return match_skills_for_prompt(discover_skills(root), prompt)


def _build_runner_input(prompt: str, image_data_urls: list[str]) -> str | list[dict[str, Any]]:
    if not image_data_urls:
        return prompt
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    content.extend({"type": "input_image", "image_url": url} for url in image_data_urls)
    return [{"role": "user", "content": content}]


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


def _pending_questions_from_tool_output(output: str) -> list[dict[str, Any]]:
    if not output.strip():
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
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
