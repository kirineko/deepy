from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any, cast


def sanitize_model_input_for_chat_completions(input_value: Any) -> Any:
    if not isinstance(input_value, list):
        return input_value
    return sanitize_replay_items(input_value)


def sanitize_sdk_items_for_replay(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], sanitize_replay_items(items))


def sanitize_replay_items(items: Iterable[Any]) -> list[Any]:
    item_list = list(items)
    remaining_outputs = Counter(
        call_id
        for item in item_list
        if _item_type(item) == "function_call_output" and (call_id := _call_id(item))
    )
    open_call_ids: set[str] = set()
    sanitized: list[Any] = []

    for item in item_list:
        item_type = _item_type(item)
        if item_type == "function_call":
            sanitized.append(item)
            if call_id := _call_id(item):
                open_call_ids.add(call_id)
            continue

        if item_type == "function_call_output":
            if call_id := _call_id(item):
                if remaining_outputs[call_id] > 0:
                    remaining_outputs[call_id] -= 1
                open_call_ids.discard(call_id)
            sanitized.append(item)
            continue

        if _is_empty_assistant_message(item) and any(
            remaining_outputs[call_id] > 0 for call_id in open_call_ids
        ):
            continue

        sanitized.append(item)

    return sanitized


def sanitize_model_response_output(items: list[Any]) -> list[Any]:
    return [item for item in items if not _is_empty_assistant_message(item)]


def sanitize_chat_completion_stream_event(event: Any) -> Any | None:
    if getattr(event, "type", None) == "response.output_item.done" and _is_empty_assistant_message(
        getattr(event, "item", None)
    ):
        return None

    if getattr(event, "type", None) == "response.completed":
        response = getattr(event, "response", None)
        output = getattr(response, "output", None)
        if isinstance(output, list):
            try:
                response.output = sanitize_model_response_output(output)
            except Exception:
                pass
    return event


def _is_empty_assistant_message(item: Any) -> bool:
    if _item_type(item) != "message" or _role(item) != "assistant":
        return False

    content = _get_value(item, "content")
    if content in ("", None, []):
        return True
    if isinstance(content, str):
        return not content.strip()
    if not isinstance(content, list):
        return False

    saw_text_part = False
    for part in content:
        text = _get_value(part, "text")
        if text is None:
            text = _get_value(part, "refusal")
        if not isinstance(text, str):
            return False
        saw_text_part = True
        if text.strip():
            return False
    return saw_text_part


def _item_type(item: Any) -> str:
    value = _get_value(item, "type")
    return value if isinstance(value, str) else ""


def _role(item: Any) -> str:
    value = _get_value(item, "role")
    return value if isinstance(value, str) else ""


def _call_id(item: Any) -> str:
    value = _get_value(item, "call_id")
    if value is None:
        value = _get_value(item, "id")
    return value if isinstance(value, str) else ""


def _get_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)
