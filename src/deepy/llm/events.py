from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StreamKind = Literal[
    "text_delta",
    "tool_call",
    "tool_output",
    "message",
    "agent_updated",
    "unknown",
]


@dataclass(frozen=True)
class DeepyStreamEvent:
    kind: StreamKind
    text: str = ""
    name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


def normalize_stream_event(event: Any) -> DeepyStreamEvent | None:
    event_type = getattr(event, "type", None)
    if event_type == "raw_response_event":
        delta = _raw_delta(event)
        if delta:
            return DeepyStreamEvent(kind="text_delta", text=delta)
        return None

    if event_type == "agent_updated_stream_event":
        agent = getattr(event, "new_agent", None)
        name = getattr(agent, "name", "") if agent is not None else ""
        return DeepyStreamEvent(kind="agent_updated", name=name, text=name)

    if event_type != "run_item_stream_event":
        return DeepyStreamEvent(kind="unknown", name=str(event_type or ""), payload={"event": event})

    item = getattr(event, "item", None)
    name = getattr(event, "name", "")
    if name == "tool_called":
        tool_name = _tool_name(item)
        return DeepyStreamEvent(
            kind="tool_call",
            name=tool_name,
            text=tool_name,
            payload={"call_id": _call_id(item)},
        )
    if name == "tool_output":
        output = getattr(item, "output", "")
        return DeepyStreamEvent(
            kind="tool_output",
            name=_tool_name(item),
            text=output if isinstance(output, str) else str(output),
            payload={"call_id": _call_id(item)},
        )
    if name == "message_output_created":
        text = _message_text(item)
        return DeepyStreamEvent(kind="message", text=text)

    return DeepyStreamEvent(kind="unknown", name=str(name), payload={"item": item})


def _raw_delta(event: Any) -> str:
    data = getattr(event, "data", None)
    delta = getattr(data, "delta", None)
    if isinstance(delta, str):
        return delta
    return ""


def _tool_name(item: Any) -> str:
    if item is None:
        return ""
    tool_name = getattr(item, "tool_name", None)
    if isinstance(tool_name, str) and tool_name:
        return tool_name
    raw_item = getattr(item, "raw_item", None)
    if isinstance(raw_item, dict):
        value = raw_item.get("name")
        return value if isinstance(value, str) else ""
    value = getattr(raw_item, "name", "")
    return value if isinstance(value, str) else ""


def _call_id(item: Any) -> str:
    if item is None:
        return ""
    call_id = getattr(item, "call_id", None)
    if isinstance(call_id, str):
        return call_id
    raw_item = getattr(item, "raw_item", None)
    if isinstance(raw_item, dict):
        value = raw_item.get("call_id") or raw_item.get("id")
        return str(value) if value is not None else ""
    value = getattr(raw_item, "call_id", None) or getattr(raw_item, "id", None)
    return str(value) if value is not None else ""


def _message_text(item: Any) -> str:
    raw_item = getattr(item, "raw_item", None)
    content = getattr(raw_item, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            text = part.get("text") if isinstance(part, dict) else getattr(part, "text", "")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return ""
