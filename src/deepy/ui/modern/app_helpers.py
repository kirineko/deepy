from __future__ import annotations

from pathlib import Path
from typing import Any

from deepy.audit import AuditModeState
from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings
from deepy.prompts.rules import has_agents_instructions
from deepy.sessions import DeepySession
from deepy.ui.modern.app_patchable import resolve as _resolve
from deepy.ui.modern.render.status_format import (
    _active_tui_audit_mode,
    _format_tui_audit_mode,
    _format_tui_cache_status,
    _format_tui_context_window_status,
    _format_tui_status_cache_hit_rate,
)
from deepy.ui.modern.screens import SkillScreenEntry
from deepy.ui.modern.widgets import (
    AssistantBlock,
    DiffBlock,
    InfoBlock,
    LocalCommandBlock,
    ThinkingBlock,
    ToolBlock,
    UserBlock,
)
from deepy.ui.shared.render.message_view import parse_tool_output
from deepy.ui.shared.render.welcome import format_home_relative_path
from textual.widget import Widget

def _transcript_block_copy_text(block: Widget) -> str:
    if isinstance(block, UserBlock):
        return block.body
    if isinstance(block, AssistantBlock):
        return block.markdown
    if isinstance(block, ThinkingBlock):
        return block.body
    if isinstance(block, LocalCommandBlock):
        parts = [block.title, block.output_body]
        if block.meta_body:
            parts.append(block.meta_body)
        return "\n".join(part for part in parts if part)
    if isinstance(block, ToolBlock):
        parts = [block.title]
        if block.tool_name == "todo_write" and block.output_body:
            parts.append(block.output_body)
        if block.expanded and block.details:
            parts.append(block.details)
        return "\n\n".join(part for part in parts if part)
    if isinstance(block, DiffBlock):
        return block.body
    if isinstance(block, InfoBlock):
        return block.body
    body = getattr(block, "body", "")
    return body if isinstance(body, str) else ""


async def _load_session_items(project_root: Path, session_id: str) -> list[dict[str, Any]]:
    try:
        return await DeepySession.open(project_root, session_id).get_items()
    except Exception:
        return []


_SESSION_ENTRY_UNSET = object()


def _build_tui_status_context(
    session_id: str | None,
    *,
    project_root: Path,
    settings: Settings,
    background_tasks: BackgroundTaskManager | None = None,
    audit_state: AuditModeState | None = None,
    session_entry: Any = _SESSION_ENTRY_UNSET,
) -> str:
    segments = [
        f"provider {settings.model.provider}",
        f"model {settings.model.name}[{settings.model.reasoning_mode}]",
        f"cwd {format_home_relative_path(project_root)}",
        f"audit {_active_tui_audit_mode(audit_state, settings)}",
    ]
    if has_agents_instructions(project_root):
        segments.append("[AGENTS.md]")
    mcp_count = _configured_mcp_server_count(settings, project_root)
    if mcp_count > 0:
        segments.append(f"mcp {mcp_count}")
    if background_tasks is not None:
        running = background_tasks.running_count()
        if running:
            segments.append(f"bg {running}")
    if session_entry is _SESSION_ENTRY_UNSET:
        session_entry = _tui_session_entry(project_root, session_id)
    segments.append(
        _format_tui_context_window_status(
            session_entry,
            settings.context.window_tokens,
            settings.context.resolved_compact_threshold,
        )
    )
    segments.append(_format_tui_status_cache_hit_rate(session_entry))
    return " · ".join(segments)


def _format_tui_side_status(
    project_root: Path,
    settings: Settings,
    session_id: str | None,
    loaded_skill_names: list[str],
    todo_text: str,
    *,
    audit_state: AuditModeState | None = None,
    session_entry: Any = _SESSION_ENTRY_UNSET,
) -> str:
    if session_entry is _SESSION_ENTRY_UNSET:
        session_entry = _tui_session_entry(project_root, session_id)
    lines = [
        f"Project: {project_root}",
        f"Provider: {settings.model.provider}",
        f"Model: {settings.model.name}",
        f"Thinking: {settings.model.reasoning_mode}",
        f"Audit: {_format_tui_audit_mode(audit_state, settings)}",
        f"Session: {session_id or 'new'}",
        f"Cache: {_format_tui_cache_status(session_entry)}",
        f"Skills: {', '.join(loaded_skill_names) or 'none'}",
    ]
    if todo_text:
        lines.extend(["", "Todos:", todo_text])
    return "\n".join(lines)


def _tui_session_entry(project_root: Path, session_id: str | None) -> Any | None:
    if not session_id:
        return None
    try:
        return next(
            (entry for entry in _resolve("list_session_entries")(project_root) if entry.id == session_id),
            None,
        )
    except Exception:
        return None


def _configured_mcp_server_count(settings: Settings, project_root: Path) -> int:
    try:
        return len(_resolve("load_mcp_config")(settings, project_root=project_root).definitions)
    except Exception:
        return 0


def _installed_skill_entries(project_root: Path) -> list[SkillScreenEntry]:
    records = {record.name.lower(): record for record in _resolve("list_installed_skills")()}
    entries: list[SkillScreenEntry] = []
    seen: set[str] = set()
    for skill in _resolve("discover_skills")(project_root):
        if skill.scope == "builtin":
            continue
        record = records.get(skill.name.lower())
        entries.append(
            SkillScreenEntry(
                name=skill.name,
                scope=record.scope if record is not None else skill.scope,
                description=skill.description,
                version=record.version if record is not None else "",
                path=str(record.install_path if record is not None else skill.path.parent),
                installed=True,
                managed_by_market=record is not None,
                source="installed",
                removable=skill.scope != "builtin",
            )
        )
        seen.add(skill.name.lower())
    for record in records.values():
        if record.name.lower() in seen:
            continue
        entries.append(
            SkillScreenEntry(
                name=record.name,
                scope=record.scope,
                version=record.version,
                path=str(record.install_path),
                installed=True,
                managed_by_market=True,
                source="installed",
                removable=True,
            )
        )
    return sorted(entries, key=lambda entry: (entry.scope != "project", entry.name))


def _tool_output_diff_text(output: str) -> str | None:
    view = parse_tool_output(output)
    if view.ok is not True or view.name not in {"Write", "Update"}:
        return None
    return view.diff_preview or view.diff


def _widget_appears_before(left: Widget, right: Widget) -> bool:
    parent = left.parent
    if parent is None or parent is not right.parent:
        return False
    siblings = list(parent.children)
    try:
        return siblings.index(left) < siblings.index(right)
    except ValueError:
        return False




