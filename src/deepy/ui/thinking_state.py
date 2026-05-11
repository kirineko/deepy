from __future__ import annotations

from typing import Any, Iterable, Mapping


def find_expanded_thinking_id(messages: Iterable[Any]) -> str | None:
    expanded: str | None = None
    for message in messages:
        if _field(message, "role") != "assistant":
            continue
        if _is_thinking_message(message):
            message_id = _field(message, "id")
            expanded = message_id if isinstance(message_id, str) else None
        else:
            expanded = None
    return expanded


def _is_thinking_message(message: Any) -> bool:
    meta = _field(message, "meta")
    if isinstance(meta, Mapping):
        return meta.get("asThinking") is True
    return getattr(meta, "asThinking", False) is True


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)
