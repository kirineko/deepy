from __future__ import annotations

from collections.abc import Callable
from typing import Any

from deepy.llm.events import DeepyStreamEvent
from deepy.ui.shared.render.message_view import parse_tool_output
from deepy.utils import json as json_utils

ItemTextFn = Callable[[dict[str, Any]], str]
ToolOutputTextFn = Callable[[dict[str, Any]], str]


def role(item: dict[str, Any]) -> str:
    value = item.get("role")
    return value if isinstance(value, str) else ""


def item_type(item: dict[str, Any]) -> str:
    value = item.get("type")
    return value if isinstance(value, str) else ""


def call_id(item: dict[str, Any]) -> str:
    for key in ("call_id", "tool_call_id", "id"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


def tool_call_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, str) and name:
        return name
    function = item.get("function")
    if isinstance(function, dict):
        function_name = function.get("name")
        if isinstance(function_name, str) and function_name:
            return function_name
    return "tool"


def tool_call_arguments(item: dict[str, Any]) -> str:
    arguments = item.get("arguments")
    if isinstance(arguments, str):
        return arguments
    if arguments is not None:
        return json_utils.dumps(arguments)
    function = item.get("function")
    if isinstance(function, dict):
        function_arguments = function.get("arguments")
        if isinstance(function_arguments, str):
            return function_arguments
        if function_arguments is not None:
            return json_utils.dumps(function_arguments)
    return ""


def history_tool_call_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return DeepyStreamEvent(
        kind="tool_call",
        name=tool_call_name(item),
        payload={
            "call_id": call_id(item),
            "arguments": tool_call_arguments(item),
        },
    )


def history_tool_output_event(
    item: dict[str, Any],
    tool_output_text: ToolOutputTextFn,
) -> DeepyStreamEvent:
    return DeepyStreamEvent(
        kind="tool_output",
        payload={"call_id": call_id(item)},
        text=tool_output_text(item),
    )


def is_waiting_tool_output(
    item: dict[str, Any],
    tool_output_text: ToolOutputTextFn,
) -> bool:
    if item_type(item) != "function_call_output" and role(item) != "tool":
        return False
    return parse_tool_output(tool_output_text(item)).await_user_response


def is_failed_tool_output(
    item: dict[str, Any],
    tool_output_text: ToolOutputTextFn,
) -> bool:
    if item_type(item) != "function_call_output" and role(item) != "tool":
        return False
    return parse_tool_output(tool_output_text(item)).ok is False


def session_title(items: list[dict[str, Any]], item_text: ItemTextFn) -> str:
    for item in items:
        if role(item) == "user":
            text = item_text(item)
            if text.strip():
                return text
    for item in items:
        text = item_text(item)
        if text.strip():
            return text
    return "Untitled"


def session_status(items: list[dict[str, Any]], tool_output_text: ToolOutputTextFn) -> str:
    if not items:
        return "empty"
    for item in reversed(items):
        if role(item) == "user":
            break
        if is_waiting_tool_output(item, tool_output_text):
            return "waiting"
    last = items[-1]
    if item_type(last) == "function_call":
        return "interrupted"
    if is_failed_tool_output(last, tool_output_text):
        return "failed"
    return "completed"
