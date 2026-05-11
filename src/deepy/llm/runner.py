from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepy.config import Settings, load_settings
from deepy.sessions import DeepyJsonlSession
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
    try:
        result = Runner.run_streamed(
            agent,
            input=prompt,
            max_turns=max_turns,
            run_config=run_config,
            session=session,
        )
        async for event in result.stream_events():
            normalized = normalize_stream_event(event)
            if normalized is None:
                continue
            if emit_event is not None:
                emit_event(normalized)
            if normalized.kind != "text_delta" or not normalized.text:
                continue
            chunks.append(normalized.text)
            if emit is not None:
                emit(normalized.text)
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
                "request": {"input": prompt, "max_turns": max_turns},
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
                "request": {"input": prompt, "max_turns": max_turns},
                "response": {"output": output},
            }
        )
    if resolved_settings.notify.enabled and resolved_settings.notify.command:
        launch_notify_script(resolved_settings.notify.command, duration_ms, root)
    return RunSummary(
        output=output,
        session_id=session.session_id,
        complete=bool(getattr(result, "is_complete", True)),
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
