"""Pure transcript-item and session parsing helpers for the Modern UI.

These functions translate raw session/stream items into display text. They have
no Textual dependencies and call no monkeypatched runtime entry points, so they
live outside :mod:`deepy.ui.modern.app`.
"""

from __future__ import annotations

from typing import Any

from deepy.llm.events import DeepyStreamEvent
from deepy.llm.multimodal import redacted_content_text
from deepy.ui.shared.session.session_list import format_session_title
from deepy.ui.shared.session.session_picker import ResumeSessionPreview, format_session_time
from deepy.ui.shared.session.session_transcript import (
    history_tool_output_event,
    session_status,
    session_title,
)
from deepy.utils import json as json_utils


def _session_title(items: list[dict[str, Any]]) -> str:
    return session_title(items, _visible_item_text)


def _session_status(items: list[dict[str, Any]]) -> str:
    return session_status(items, _tool_output_text)


def _format_tui_session_label(preview: ResumeSessionPreview) -> str:
    title = format_session_title(preview.title, max_chars=36)
    return (
        f"{title}  {format_session_time(preview.updated_at)}"
        f" · {preview.status}"
        f" · {preview.active_tokens:,} tokens"
        f" · {preview.id[:8]}"
    )


def _is_local_command_tool_output(view: Any) -> bool:
    metadata = getattr(view, "metadata", None) or {}
    return getattr(view, "name", "") == "shell" and bool(metadata.get("localCommandMode"))


def _visible_item_text(item: dict[str, Any]) -> str:
    if "content" in item:
        return _item_text(item["content"])
    if "text" in item:
        return _item_text(item["text"])
    if "output" in item:
        return _item_text(item["output"])
    return ""


def _raw_tool_call_event(event: DeepyStreamEvent) -> DeepyStreamEvent | None:
    if event.name != "response.output_item.added":
        return None
    raw = event.payload.get("raw")
    item = _raw_value(raw, "item")
    if item is None:
        return None
    item_type = _raw_str(item, "type")
    if item_type not in {"function_call", "custom_tool_call", "mcp_call"}:
        return None
    call_id = _raw_call_id(item)
    if not call_id:
        return None
    tool_name = _raw_tool_name(item)
    arguments = _raw_tool_arguments(item)
    return DeepyStreamEvent(
        kind="tool_call",
        name=tool_name,
        payload={"call_id": call_id, "arguments": arguments},
    )


def _history_tool_output_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return history_tool_output_event(item, _tool_output_text)


def _item_text(content: Any) -> str:
    if isinstance(content, str):
        return redacted_content_text(content)
    if isinstance(content, list):
        return redacted_content_text(content)
    if content is None:
        return ""
    if isinstance(content, dict):
        image_text = redacted_content_text(content)
        if image_text:
            return image_text
        text = _content_part_text(content)
        return text or json_utils.dumps(content)
    return str(content)


def _reasoning_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("content", "summary", "text"):
        if key in item:
            text = _item_text(item[key])
            if text.strip():
                parts.append(text)
    return "\n".join(parts)


def _tool_output_text(item: dict[str, Any]) -> str:
    if "output" in item:
        return _item_text(item["output"])
    content = item.get("content")
    if isinstance(content, list):
        return json_utils.dumps(content)
    return _item_text(content)


def _content_part_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""
    for key in ("text", "input_text", "output_text", "refusal"):
        value = part.get(key)
        if isinstance(value, str):
            return value
    return ""


def _chat_tool_calls(item: dict[str, Any]) -> list[dict[str, Any]]:
    value = item.get("tool_calls")
    if not isinstance(value, list):
        return []
    return [tool_call for tool_call in value if isinstance(tool_call, dict)]


def _raw_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _raw_str(item: Any, key: str) -> str:
    value = _raw_value(item, key)
    return value if isinstance(value, str) else ""


def _raw_call_id(item: Any) -> str:
    for key in ("call_id", "tool_call_id", "id"):
        value = _raw_str(item, key)
        if value:
            return value
    return ""


def _raw_tool_name(item: Any) -> str:
    for key in ("name", "tool_name"):
        value = _raw_str(item, key)
        if value:
            return value
    function = _raw_value(item, "function")
    value = _raw_str(function, "name")
    return value or "tool"


def _raw_tool_arguments(item: Any) -> str:
    arguments = _raw_value(item, "arguments")
    if isinstance(arguments, str):
        return arguments
    if arguments is not None:
        return json_utils.dumps(arguments)
    function = _raw_value(item, "function")
    function_arguments = _raw_value(function, "arguments")
    if isinstance(function_arguments, str):
        return function_arguments
    if function_arguments is not None:
        return json_utils.dumps(function_arguments)
    return ""


def _recoverable_tool_key(name: str, argument_summary: str) -> tuple[str, str] | None:
    if name not in {"Write", "Update"}:
        return None
    target = _recoverable_tool_target(argument_summary)
    if not target:
        return None
    return name, target


def _recoverable_tool_target(argument_summary: str) -> str:
    text = " ".join(argument_summary.strip().split())
    if not text:
        return ""
    if ":" in text:
        text = text.rsplit(":", 1)[1].strip()
    if "," in text:
        text = text.split(",", 1)[0].strip()
    if " (" in text:
        text = text.split(" (", 1)[0].strip()
    for prefix in ("malformed args, ", "file: ", "files: "):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text
