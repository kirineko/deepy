from __future__ import annotations

import re
from typing import Any

MAX_SUMMARY_CHARS = 160
TOOL_DISPLAY_LABELS = {
    "AskUserQuestion": "AskUserQuestion",
    "Read": "Read",
    "Search": "Search",
    "Update": "Update",
    "WebFetch": "WebFetch",
    "WebSearch": "WebSearch",
    "Write": "Write",
    "mcp": "MCP",
    "shell": "Shell",
    "task_list": "Tasks",
    "task_output": "Task Output",
    "task_stop": "Stop Task",
    "todo_write": "Todo",
    "load_skill": "Load Skill",
}


def format_tool_display_name(name: str) -> str:
    if name.startswith("subagent_"):
        return "Subagent"
    if name in TOOL_DISPLAY_LABELS:
        return TOOL_DISPLAY_LABELS[name]
    stripped = name.strip()
    if not stripped:
        return "Tool"
    return _display_title(stripped)


def format_tool_display_label(name: str) -> str:
    if name.startswith("subagent_"):
        subagent_name = name.removeprefix("subagent_").replace("_", "-")
        return f"[Subagent] {subagent_name}"
    return f"[{format_tool_display_name(name)}]"


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


def _display_title(value: str) -> str:
    parts = [part for part in re.split(r"[_\-\s]+", value) if part]
    if not parts:
        return "Tool"
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _first_nonempty_line(value: str) -> str | None:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _string_key_dict(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


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


def _text_size_summary(text: str) -> str:
    line_count = len(text.splitlines())
    line_label = "line" if line_count == 1 else "lines"
    return f"{line_count:,} {line_label}, {len(text):,} chars"


def _shorten_project_path(path: str, *, project_root: str | None) -> str:
    if project_root:
        root = project_root.rstrip("/\\")
        if path == root:
            return "."
        for separator in ("/", "\\"):
            prefix = f"{root}{separator}"
            if path.startswith(prefix):
                return path[len(prefix) :]
    return path
