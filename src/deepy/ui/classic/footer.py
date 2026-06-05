from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from deepy.audit import AuditModeState
from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings
from deepy.format_tokens import format_token_count_short as _format_token_count_short
from deepy.llm.cache_context import format_cache_hit_rate, format_cache_usage
from deepy.llm.runner import RunSummary
from deepy.mcp import DeepyMcpRuntime
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.prompts.rules import has_agents_instructions
from deepy.sessions import SessionEntry
from deepy.ui.classic.prompt.prompt_input import build_prompt_toolbar
from deepy.ui.classic.runtime_workers import _StartupState
from deepy.ui.classic.status.runtime_status import _format_duration_ms
from deepy.ui.classic.status.status_footer import StatusFooter, StatusFooterSegment
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette
from deepy.ui.shared.render.welcome import format_home_relative_path
from deepy.usage import TokenUsage, context_window_usage, format_usage_line
from rich.console import Console

def _print_usage_footer(
    console: Console,
    summary: RunSummary,
    *,
    settings: Settings | None = None,
    project_root: Path | None = None,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    if summary.usage.known:
        duration = _format_duration_ms(summary.duration_ms) if summary.duration_ms > 0 else ""
        prefix = f"time {duration} · " if duration else ""
        console.print(
            f"[{palette.muted}]turn Token Usage[/] {prefix}{_format_turn_usage_line(summary.usage)}"
        )
    elif summary.duration_ms > 0:
        console.print(f"[{palette.muted}]turn time[/] {_format_duration_ms(summary.duration_ms)}")


def _format_context_footer(
    session_id: str | None,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
    background_tasks: BackgroundTaskManager | None = None,
    startup_state: _StartupState | None = None,
    audit_mode: AuditModeState | None = None,
) -> str:
    return _build_status_footer(
        session_id,
        project_root=project_root,
        settings=settings,
        mcp_runtime=mcp_runtime,
        background_tasks=background_tasks,
        startup_state=startup_state,
        audit_mode=audit_mode,
    ).plain


def _build_prompt_toolbar_provider(
    session_id: str | None,
    *,
    project_root: Path,
    settings: Settings,
    mcp_runtime: DeepyMcpRuntime,
    background_tasks: BackgroundTaskManager,
    startup_state: _StartupState,
    audit_state: AuditModeState | None = None,
) -> Callable[[], object]:
    captured_session_id = session_id
    captured_settings = settings

    def toolbar() -> object:
        return build_prompt_toolbar(
            _build_status_footer(
                captured_session_id,
                project_root=project_root,
                settings=captured_settings,
                mcp_runtime=mcp_runtime,
                background_tasks=background_tasks,
                startup_state=startup_state,
                audit_mode=audit_state,
            )
        )

    return toolbar


def _build_status_footer(
    session_id: str | None,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
    background_tasks: BackgroundTaskManager | None = None,
    startup_state: _StartupState | None = None,
    active_work: str | None = None,
    audit_mode: AuditModeState | str | None = None,
) -> StatusFooter:
    if settings is None:
        return StatusFooter(())

    segments = [
        StatusFooterSegment(f"provider {settings.model.provider}", "identity"),
        StatusFooterSegment(
            f"model {settings.model.name}[{settings.model.reasoning_mode}]",
            "identity",
        ),
        StatusFooterSegment(f"audit {_audit_mode_label(audit_mode, settings)}", "metadata"),
    ]
    if project_root is not None:
        segments.append(StatusFooterSegment(f"cwd {format_home_relative_path(project_root)}", "metadata"))
        if has_agents_instructions(project_root):
            segments.append(StatusFooterSegment("[AGENTS.md]", "loaded"))
        if mcp_runtime is not None and mcp_runtime.active_servers:
            segments.append(StatusFooterSegment(f"mcp {len(mcp_runtime.active_servers)}", "loaded"))
        elif startup_state is not None:
            startup_snapshot = startup_state.snapshot()
            if startup_snapshot.mcp_pending:
                segments.append(StatusFooterSegment("mcp connecting", "metadata"))
            elif startup_snapshot.mcp_failed:
                segments.append(StatusFooterSegment("mcp failed", "metadata"))
        if startup_state is not None:
            startup_snapshot = startup_state.snapshot()
            if startup_snapshot.update_pending:
                segments.append(StatusFooterSegment("update checking", "metadata"))
        if background_tasks is not None:
            running_background_tasks = background_tasks.running_count()
            if running_background_tasks:
                segments.append(StatusFooterSegment(f"bg {running_background_tasks}", "loaded"))
    else:
        segments.append(StatusFooterSegment("cwd unknown", "metadata"))

    session_entry = _session_entry(project_root, session_id)
    segments.extend(
        [
        StatusFooterSegment(
            _format_context_window_status(
                session_entry,
                settings.context.window_tokens,
                settings.context.resolved_compact_threshold,
            ),
            "context",
        ),
        StatusFooterSegment(_format_session_cache_hit_rate(session_entry), "context"),
        ]
    )
    return StatusFooter(tuple(segments)).with_active(active_work)


def _audit_mode_label(audit_mode: AuditModeState | str | None, settings: Settings) -> str:
    if isinstance(audit_mode, AuditModeState):
        return audit_mode.mode.value
    if isinstance(audit_mode, str) and audit_mode:
        return audit_mode
    return settings.audit.mode.value


def _format_session_cache_hit_rate(session_entry: SessionEntry | None) -> str:
    if session_entry is None:
        return "cache --"
    hit_rate = format_cache_hit_rate(session_entry.cache_usage)
    if hit_rate == "unknown":
        return "cache --"
    return f"cache {hit_rate}"


def _format_session_cache_for_list(entry: SessionEntry) -> str:
    parts = []
    if entry.cache_prefix_generation:
        parts.append(f"gen {entry.cache_prefix_generation}")
    usage = format_cache_usage(entry.cache_usage)
    if usage != "unknown":
        parts.append(usage)
    if entry.cache_break_reason:
        parts.append(f"break {entry.cache_break_reason}")
    return " · ".join(parts) if parts else "unknown"


def _format_context_window_status(
    session_entry: SessionEntry | None,
    window_tokens: int,
    compact_threshold: int,
) -> str:
    window_text = _format_token_count_short(window_tokens)
    if window_tokens <= 0:
        return "ctx unknown"
    if session_entry is not None and session_entry.latest_context_window_tokens is not None:
        used_tokens = session_entry.latest_context_window_tokens
    else:
        usage_payload = session_entry.usage if session_entry is not None else None
        usage = (
            context_window_usage(usage_payload)
            if isinstance(usage_payload, dict) and usage_payload.get("request_usage_entries")
            else None
        )
        used_tokens = usage.used_tokens if usage is not None else None
    if used_tokens is None:
        return f"ctx unknown/{window_text}"
    percentage = used_tokens / window_tokens * 100
    status = f"ctx {_format_token_count_short(used_tokens)}/{window_text} ({percentage:.1f}%)"
    if compact_threshold > 0 and used_tokens >= compact_threshold:
        status = f"{status} · compact next"
    return status


def _session_entry(project_root: Path | None, session_id: str | None) -> SessionEntry | None:
    if not session_id:
        return None
    if project_root is None:
        return None
    try:
        entries = _resolve("list_session_entries")(project_root)
    except Exception:
        return None
    entry = next((item for item in entries if item.id == session_id), None)
    return entry


def _format_turn_usage_line(usage: TokenUsage) -> str:
    prefix = f"requests {usage.requests:,} · " if usage.requests > 0 else ""
    return f"{prefix}{format_usage_line(usage)}"

