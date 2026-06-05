from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast

from deepy.audit import ApprovalDecision, PendingApproval
from deepy.tools import ToolRuntime
from deepy.utils import json as json_utils


async def _approval_decisions(
    interruptions: list[Any],
    *,
    approval_resolver: Callable[
        [list[PendingApproval]],
        list[ApprovalDecision] | Awaitable[list[ApprovalDecision]],
    ]
    | None,
    runtime: ToolRuntime | None = None,
) -> list[ApprovalDecision]:
    pending = [
        _pending_approval_from_interruption(index, item, runtime=runtime)
        for index, item in enumerate(interruptions)
    ]
    if approval_resolver is None:
        return [
            ApprovalDecision(
                outcome="reject",
                rejection_message="Tool execution requires audit approval, but no approval UI is available.",
            )
            for _ in pending
        ]
    resolved = approval_resolver(pending)
    if inspect.isawaitable(resolved):
        resolved = await resolved
    decisions = list(cast(list[ApprovalDecision], resolved))
    if len(decisions) < len(pending):
        decisions = [
            *decisions,
            *[
                ApprovalDecision(
                    outcome="reject",
                    rejection_message="Tool execution was rejected because no audit decision was provided.",
                )
                for _ in range(len(pending) - len(decisions))
            ],
        ]
    return decisions[: len(pending)]


def _pending_approval_from_interruption(
    index: int,
    item: Any,
    *,
    runtime: ToolRuntime | None = None,
) -> PendingApproval:
    raw_item = getattr(item, "raw_item", None)
    tool_name = _approval_tool_name(item, raw_item)
    arguments = _approval_arguments(item, raw_item)
    agent = getattr(item, "agent", None)
    agent_name = str(getattr(agent, "name", "") or "")
    server_name = _approval_server_name(raw_item, tool_name)
    preflight = _approval_preflight(runtime, tool_name, arguments)
    return PendingApproval(
        index=index,
        name=str(getattr(item, "name", "") or tool_name or "tool"),
        tool_name=tool_name,
        arguments=arguments,
        call_id=_approval_call_id(item, raw_item),
        agent_name=agent_name,
        action_kind="mcp_tool" if server_name else _approval_action_kind(tool_name),
        server_name=server_name,
        preflight=preflight,
    )


def _approval_preflight(
    runtime: ToolRuntime | None,
    tool_name: str,
    arguments: str,
) -> dict[str, Any] | None:
    if runtime is None or tool_name not in {"Write", "Update"}:
        return None
    try:
        result = runtime.preflight_file_mutation(tool_name, arguments)
    except Exception as exc:
        return {
            "ok": False,
            "name": tool_name,
            "output": "",
            "error": f"Preflight failed: {exc}",
            "metadata": {"preflight": True},
        }
    return dict(result)


def _approval_tool_name(item: Any, raw_item: Any) -> str:
    for value in (
        getattr(item, "tool_name", None),
        getattr(item, "name", None),
        getattr(raw_item, "name", None),
    ):
        if isinstance(value, str) and value:
            return value
    if isinstance(raw_item, dict):
        value = raw_item.get("name")
        if isinstance(value, str):
            return value
        function = raw_item.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            return function["name"]
    return ""


def _approval_arguments(item: Any, raw_item: Any) -> str:
    for value in (getattr(item, "arguments", None), getattr(raw_item, "arguments", None)):
        if isinstance(value, str):
            return value
    if isinstance(raw_item, dict):
        value = raw_item.get("arguments")
        if isinstance(value, str):
            return value
        function = raw_item.get("function")
        if isinstance(function, dict) and isinstance(function.get("arguments"), str):
            return function["arguments"]
        arguments = raw_item.get("arguments_json") or raw_item.get("input")
        if arguments is not None:
            return json_utils.dumps(arguments)
    arguments = getattr(raw_item, "arguments_json", None)
    if arguments is not None:
        return json_utils.dumps(arguments)
    return ""


def _approval_call_id(item: Any, raw_item: Any) -> str:
    for value in (
        getattr(item, "call_id", None),
        getattr(raw_item, "call_id", None),
        getattr(raw_item, "tool_call_id", None),
        getattr(raw_item, "id", None),
    ):
        if isinstance(value, str) and value:
            return value
    if isinstance(raw_item, dict):
        for key in ("call_id", "tool_call_id", "id"):
            value = raw_item.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _approval_server_name(raw_item: Any, tool_name: str) -> str:
    for attr in ("server_label", "server_name"):
        value = getattr(raw_item, attr, None)
        if isinstance(value, str) and value:
            return value
    if isinstance(raw_item, dict):
        for key in ("server_label", "server_name"):
            value = raw_item.get(key)
            if isinstance(value, str) and value:
                return value
    if "__" in tool_name:
        return tool_name.split("__", 1)[0]
    return ""


def _approval_action_kind(tool_name: str) -> str:
    if tool_name in {"Write", "Update"}:
        return "text_write"
    if tool_name in {"shell", "test_shell"}:
        return "command"
    if tool_name == "task_stop":
        return "background_task_control"
    return "tool"
