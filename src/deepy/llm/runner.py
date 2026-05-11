from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepy.config import Settings, load_settings
from deepy.sessions import DeepyJsonlSession
from deepy.tools import ToolRuntime

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
) -> RunSummary:
    from agents import RunConfig, Runner

    root = (project_root or Path.cwd()).resolve()
    resolved_settings = settings or load_settings()
    resolved_provider = provider or build_provider_bundle(resolved_settings)
    runtime = ToolRuntime(cwd=root, settings=resolved_settings)
    agent = build_deepy_agent(
        resolved_settings,
        runtime,
        project_root=root,
        provider=resolved_provider,
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

    result = Runner.run_streamed(
        agent,
        input=prompt,
        max_turns=max_turns,
        run_config=run_config,
        session=session,
    )
    chunks: list[str] = []
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

    final_output = getattr(result, "final_output", None)
    output = final_output if isinstance(final_output, str) else "".join(chunks)
    return RunSummary(
        output=output,
        session_id=session.session_id,
        complete=bool(getattr(result, "is_complete", True)),
    )
