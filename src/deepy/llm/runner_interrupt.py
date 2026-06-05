from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any, Literal

from deepy.sessions import DeepySession
from deepy.utils import json as json_utils

INTERRUPTED_MARKER_TEXT = (
    "Interrupted by user with Esc. This turn was stopped before completion. "
    "Do not continue the interrupted request unless the user explicitly asks to continue."
)
INTERRUPTED_TOOL_OUTPUT_TEXT = "Tool execution interrupted by user with Esc."


def _cancel_stream_result(
    result: Any,
    *,
    mode: Literal["immediate", "after_turn"],
) -> None:
    cancel = getattr(result, "cancel", None)
    if not callable(cancel):
        return
    try:
        cancel(mode=mode)
    except TypeError:
        cancel()


async def _watch_stream_interrupt(
    result: Any,
    *,
    should_interrupt: Callable[[], bool],
    cancel_mode: Literal["immediate", "after_turn"],
) -> bool:
    while not bool(getattr(result, "is_complete", False)):
        if should_interrupt():
            _cancel_stream_result(result, mode=cancel_mode)
            return True
        await asyncio.sleep(0.05)
    return False


async def _finish_interrupt_task(task: asyncio.Task[bool] | None) -> bool:
    if task is None:
        return False
    if task.done():
        return task.result()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return False


async def _reconcile_interrupted_session_tail(
    session: DeepySession,
    *,
    baseline_count: int,
    prompt: str,
) -> None:
    items = await session.get_items()
    if baseline_count < 0 or baseline_count > len(items):
        return
    suffix = items[baseline_count:]
    if not suffix:
        return

    if len(suffix) == 1 and _is_user_prompt_item(suffix[0], prompt):
        await session.pop_item()
        return

    additions = _interrupted_tool_output_items(suffix)
    if not _is_interrupt_marker_item(suffix[-1]):
        additions.append(_interrupted_marker_item())
    if additions:
        await session.add_items(additions)


def _is_user_prompt_item(item: dict[str, Any], prompt: str) -> bool:
    if item.get("role") != "user":
        return False
    return _item_text_content(item) == prompt


def _item_text_content(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for part in content:
        if isinstance(part, dict):
            text = part.get("text")
            if text is None:
                text = part.get("input_text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _interrupted_tool_output_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output_call_ids = {
        call_id
        for item in items
        if (call_id := _function_call_output_id(item))
    }
    additions: list[dict[str, Any]] = []
    added_call_ids: set[str] = set()
    for item in items:
        for call_id, output_item in _missing_output_items_for_call(item, output_call_ids):
            if call_id in added_call_ids:
                continue
            additions.append(output_item)
            added_call_ids.add(call_id)
    return additions


def _missing_output_items_for_call(
    item: dict[str, Any],
    output_call_ids: set[str],
) -> list[tuple[str, dict[str, Any]]]:
    call_id = _function_call_id(item)
    if call_id:
        return (
            []
            if call_id in output_call_ids
            else [
                (
                    call_id,
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": INTERRUPTED_TOOL_OUTPUT_TEXT,
                    },
                )
            ]
        )

    missing: list[tuple[str, dict[str, Any]]] = []
    if item.get("role") != "assistant":
        return missing
    tool_calls = item.get("tool_calls")
    if not isinstance(tool_calls, list):
        return missing
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        chat_call_id = tool_call.get("id")
        if not isinstance(chat_call_id, str) or not chat_call_id or chat_call_id in output_call_ids:
            continue
        missing.append(
            (
                chat_call_id,
                {
                    "role": "tool",
                    "tool_call_id": chat_call_id,
                    "content": INTERRUPTED_TOOL_OUTPUT_TEXT,
                },
            )
        )
    return missing


def _function_call_id(item: dict[str, Any]) -> str:
    if item.get("type") != "function_call":
        return ""
    call_id = item.get("call_id")
    if call_id is None:
        call_id = item.get("id")
    return call_id if isinstance(call_id, str) else ""


def _function_call_output_id(item: dict[str, Any]) -> str:
    if item.get("type") == "function_call_output":
        call_id = item.get("call_id")
        return call_id if isinstance(call_id, str) else ""
    if item.get("role") == "tool":
        tool_call_id = item.get("tool_call_id")
        return tool_call_id if isinstance(tool_call_id, str) else ""
    return ""


def _interrupted_marker_item() -> dict[str, Any]:
    return {"role": "assistant", "content": INTERRUPTED_MARKER_TEXT}


def _is_interrupt_marker_item(item: dict[str, Any]) -> bool:
    return item.get("role") == "assistant" and item.get("content") == INTERRUPTED_MARKER_TEXT


def _pending_questions_from_tool_output(output: str) -> list[dict[str, Any]]:
    if not output.strip():
        return []
    try:
        payload = json_utils.loads(output)
    except json_utils.JSONDecodeError:
        return []
    if not isinstance(payload, dict) or payload.get("awaitUserResponse") is not True:
        return []
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("kind") != "ask_user_question":
        return []
    questions = metadata.get("questions")
    if not isinstance(questions, list):
        return []
    return [question for question in questions if isinstance(question, dict)]
