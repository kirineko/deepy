from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StreamKind = Literal[
    "text_delta",
    "reasoning_delta",
    "reasoning_item",
    "tool_call",
    "tool_output",
    "message",
    "agent_updated",
    "usage",
    "raw_response",
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
        data = getattr(event, "data", None)
        data_type = getattr(data, "type", "")
        delta = _raw_delta(event)
        if data_type == "response.reasoning_summary_text.delta" and delta:
            return DeepyStreamEvent(kind="reasoning_delta", text=delta, payload={"raw": data})
        if delta:
            return DeepyStreamEvent(kind="text_delta", text=delta)
        if data_type == "response.completed":
            usage = _response_usage(data)
            return DeepyStreamEvent(
                kind="usage",
                payload={"usage": usage, "raw": data},
            )
        return DeepyStreamEvent(kind="raw_response", name=str(data_type or ""), payload={"raw": data})

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
    if name == "reasoning_item_created":
        return DeepyStreamEvent(kind="reasoning_item", payload={"item": item})

    return DeepyStreamEvent(kind="unknown", name=str(name), payload={"item": item})


def _raw_delta(event: Any) -> str:
    data = getattr(event, "data", None)
    delta = getattr(data, "delta", None)
    if isinstance(delta, str):
        return delta
    return ""


def _response_usage(data: Any) -> Any:
    response = getattr(data, "response", None)
    usage = getattr(response, "usage", None)
    return _to_payload(usage)


def _to_payload(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return value


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
