from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class SessionChoice(Protocol):
    id: str
    updated_at: int
    active_tokens: int


def format_session_title(value: str | None, max_chars: int = 70) -> str:
    title = " ".join((value or "Untitled").split()).strip() or "Untitled"
    return _truncate(title, max_chars)


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


def _truncate(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "…"
