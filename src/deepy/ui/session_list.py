from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar


T = TypeVar("T")


class SessionChoice(Protocol):
    id: str
    updated_at: int
    active_tokens: int


@dataclass(frozen=True)
class SessionListWindow:
    safe_index: int
    scroll_offset: int
    max_visible: int


def format_session_title(value: str | None, max_chars: int = 70) -> str:
    title = " ".join((value or "Untitled").split()).strip() or "Untitled"
    return _truncate(title, max_chars)


def max_visible_sessions(rows: int) -> int:
    reserved_lines = 8
    lines_per_session = 3
    available_lines = max(0, min(rows, 30) - reserved_lines)
    return max(1, available_lines // lines_per_session)


def session_list_window(
    *,
    session_count: int,
    selected_index: int,
    rows: int,
) -> SessionListWindow:
    visible = max_visible_sessions(rows)
    if session_count <= 0:
        return SessionListWindow(safe_index=0, scroll_offset=0, max_visible=visible)
    safe_index = min(max(selected_index, 0), session_count - 1)
    scroll_offset = 0 if safe_index < visible else safe_index - visible + 1
    return SessionListWindow(
        safe_index=safe_index,
        scroll_offset=scroll_offset,
        max_visible=visible,
    )


def visible_sessions(
    sessions: list[T],
    *,
    selected_index: int,
    rows: int,
) -> list[T]:
    window = session_list_window(
        session_count=len(sessions),
        selected_index=selected_index,
        rows=rows,
    )
    return sessions[window.scroll_offset : window.scroll_offset + window.max_visible]


def format_session_choice(entry: SessionChoice, index: int) -> str:
    return (
        f"{index}. {entry.id}  updated={entry.updated_at}  "
        f"history_estimate={entry.active_tokens}"
    )


def format_session_choices(entries: Sequence[SessionChoice], *, max_entries: int = 10) -> str:
    if not entries:
        return "No sessions found."
    lines = [
        format_session_choice(entry, index)
        for index, entry in enumerate(entries[:max_entries], 1)
    ]
    remaining = len(entries) - len(lines)
    if remaining > 0:
        lines.append(f"...and {remaining} more.")
    return "\n".join(lines)


def resolve_session_selection(
    entries: Sequence[SessionChoice],
    selection: str,
) -> SessionChoice | None:
    value = selection.strip()
    if not value:
        return None
    if value.isdigit():
        index = int(value) - 1
        if 0 <= index < len(entries):
            return entries[index]
    exact = [entry for entry in entries if entry.id == value]
    if len(exact) == 1:
        return exact[0]
    prefix = [entry for entry in entries if entry.id.startswith(value)]
    if len(prefix) == 1:
        return prefix[0]
    return None


def move_session_selection(
    *,
    selected_index: int,
    session_count: int,
    action: str,
    rows: int,
) -> int:
    if session_count <= 0:
        return 0
    visible = max_visible_sessions(rows)
    if action == "up":
        next_index = selected_index - 1
    elif action == "down":
        next_index = selected_index + 1
    elif action == "page_up":
        next_index = selected_index - visible
    elif action == "page_down":
        next_index = selected_index + visible
    elif action == "home":
        next_index = 0
    elif action == "end":
        next_index = session_count - 1
    else:
        next_index = selected_index
    return min(max(next_index, 0), session_count - 1)


def _truncate(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "…"
