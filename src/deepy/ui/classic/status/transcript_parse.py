from __future__ import annotations

from typing import Any

from deepy.llm.multimodal import redact_image_data_urls, redacted_content_text
from deepy.utils import json as json_utils


def _item_text(item: dict[str, Any]) -> str:
    if "content" in item:
        return _content_text(item["content"])
    if "text" in item:
        return _content_text(item["text"])
    if "output" in item:
        return _content_text(item["output"])
    return ""


def _reasoning_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("content", "summary", "text"):
        if key in item:
            text = _content_text(item[key])
            if text.strip():
                parts.append(text)
    return "\n".join(parts)


def _tool_output_text(item: dict[str, Any]) -> str:
    if "output" in item:
        return _content_text(item["output"])
    content = item.get("content")
    if isinstance(content, list):
        return json_utils.dumps(content)
    return _item_text(item)


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return redacted_content_text(value)
    if isinstance(value, list):
        return redacted_content_text(value)
    if value is None:
        return ""
    value_dict = _string_key_dict(value)
    if value_dict is not None:
        image_text = redacted_content_text(value_dict)
        if image_text:
            return image_text
        text = _content_text_part(value_dict)
        return text or json_utils.dumps(redact_image_data_urls(value_dict))
    if isinstance(value, dict):
        return json_utils.dumps(value)
    return str(value)


def _content_text_part(part: object) -> str:
    if isinstance(part, str):
        return part
    part_dict = _string_key_dict(part)
    if part_dict is None:
        return ""
    for key in ("text", "input_text", "output_text", "refusal"):
        value = part_dict.get(key)
        if isinstance(value, str):
            return value
    return ""


def _chat_tool_calls(item: dict[str, Any]) -> list[dict[str, Any]]:
    value = item.get("tool_calls")
    if not isinstance(value, list):
        return []
    return [tool_call for tool_call in value if isinstance(tool_call, dict)]


def _string_key_dict(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}
