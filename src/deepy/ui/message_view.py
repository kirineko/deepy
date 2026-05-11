from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text


MAX_SUMMARY_CHARS = 160
MAX_DIFF_LINES = 80
DIFF_PREVIEW_TOOLS = {"edit", "write"}


@dataclass(frozen=True)
class ToolOutputView:
    name: str
    ok: bool | None
    status: str
    summary: str
    output: str = ""
    error: str | None = None
    path: str | None = None
    diff: str | None = None
    await_user_response: bool = False
    raw: str = ""


def parse_tool_output(output: str) -> ToolOutputView:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return _raw_tool_output(output)

    if not isinstance(payload, dict):
        return _raw_tool_output(output)

    name = _string_or_default(payload.get("name"), "tool")
    ok = payload.get("ok")
    ok_value = ok if isinstance(ok, bool) else None
    status = _status_text(ok_value)
    metadata = payload.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    path = _string_or_none(metadata_dict.get("path"))
    diff = _string_or_none(metadata_dict.get("diff"))
    error = _string_or_none(payload.get("error"))
    text_output = _string_or_default(payload.get("output"), "")
    await_user_response = bool(payload.get("awaitUserResponse"))

    detail = (error or path or _first_nonempty_line(text_output) or "").strip()
    summary = f"{name} {status}" + (f" - {_truncate(detail)}" if detail else "")
    return ToolOutputView(
        name=name,
        ok=ok_value,
        status=status,
        summary=summary,
        output=text_output,
        error=error,
        path=path,
        diff=diff,
        await_user_response=await_user_response,
        raw=output,
    )


def format_tool_output_summary(output: str) -> str:
    return parse_tool_output(output).summary


def tool_diff_preview(output: str, *, max_lines: int = MAX_DIFF_LINES) -> str | None:
    view = parse_tool_output(output)
    if view.ok is not True or view.name not in DIFF_PREVIEW_TOOLS or not view.diff:
        return None
    return _limit_lines(view.diff, max_lines=max_lines)


def render_tool_output(output: str) -> Group:
    view = parse_tool_output(output)
    parts: list[Any] = [Text(view.summary)]
    diff = tool_diff_preview(output)
    if diff:
        parts.append(Syntax(diff.rstrip(), "diff", theme="ansi_dark", word_wrap=False))
    return Group(*parts)


def _raw_tool_output(output: str) -> ToolOutputView:
    return ToolOutputView(
        name="tool",
        ok=None,
        status="raw",
        summary=_truncate(output),
        raw=output,
    )


def _status_text(ok: bool | None) -> str:
    if ok is True:
        return "ok"
    if ok is False:
        return "failed"
    return "unknown"


def _string_or_default(value: Any, default: str) -> str:
    if isinstance(value, str):
        return value
    return default


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _first_nonempty_line(value: str) -> str | None:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _truncate(value: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 15].rstrip() + "... [truncated]"


def _limit_lines(value: str, *, max_lines: int) -> str:
    lines = value.splitlines()
    if len(lines) <= max_lines:
        return value
    omitted = len(lines) - max_lines
    return "\n".join(lines[:max_lines]) + f"\n... [truncated {omitted} diff lines]"
