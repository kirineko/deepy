from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar


T = TypeVar("T")


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
