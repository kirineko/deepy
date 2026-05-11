from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


MAX_SUMMARY_CHARS = 160
MAX_DIFF_LINES = 80
DIFF_PREVIEW_TOOLS = {"edit", "write"}
ROLE_TITLES = {
    "user": "You",
    "assistant": "Deepy",
    "system": "System",
    "developer": "Developer",
}


@dataclass(frozen=True)
class DiffPreviewLine:
    marker: str
    content: str
    kind: str


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
    diff_preview: str | None = None
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
    diff_preview = _string_or_none(metadata_dict.get("diff_preview"))
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
        diff_preview=diff_preview,
        await_user_response=await_user_response,
        raw=output,
    )


def format_tool_output_summary(output: str) -> str:
    return parse_tool_output(output).summary


def tool_diff_preview(output: str, *, max_lines: int = MAX_DIFF_LINES) -> str | None:
    view = parse_tool_output(output)
    diff = _tool_diff_text(view)
    if not diff:
        return None
    return _limit_lines(diff, max_lines=max_lines)


def tool_diff_preview_lines(output: str) -> list[DiffPreviewLine]:
    view = parse_tool_output(output)
    diff = _tool_diff_text(view)
    return parse_diff_preview(diff) if diff else []


def parse_diff_preview(diff_preview: str) -> list[DiffPreviewLine]:
    lines: list[DiffPreviewLine] = []
    for line in diff_preview.splitlines():
        if not line or line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@ "):
            continue
        if line.startswith("+"):
            lines.append(DiffPreviewLine(marker="+", content=line[1:], kind="added"))
        elif line.startswith("-"):
            lines.append(DiffPreviewLine(marker="-", content=line[1:], kind="removed"))
        else:
            lines.append(
                DiffPreviewLine(
                    marker=" ",
                    content=line[1:] if line.startswith(" ") else line,
                    kind="context",
                )
            )
    return lines


def build_thinking_summary(content: str, message_params: object | None = None) -> str:
    if content:
        normalized = " ".join(content.split())
        result = _truncate(normalized, max_chars=100)
        if result.endswith((":", "：")):
            result = result[:-1]
        return result

    if isinstance(message_params, dict):
        reasoning_content = message_params.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            return "(reasoning...)"
    return ""


def build_tool_params_snippet(tool_function: object | None, *, project_root: str | None = None) -> str:
    if not isinstance(tool_function, dict):
        return ""
    args = tool_function.get("arguments")
    tool_name = tool_function.get("name")
    if not isinstance(args, str) or not args.strip():
        return ""
    try:
        parsed = json.loads(args)
    except json.JSONDecodeError:
        return args.strip()
    if not isinstance(parsed, dict):
        return args.strip()
    return _format_tool_params_snippet(
        tool_name if isinstance(tool_name, str) else None,
        parsed,
        project_root=project_root,
    )


def build_tool_result_snippet(content: str, *, max_chars: int = 2_000) -> str:
    trimmed = content.strip()
    if not trimmed:
        return ""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return _format_tool_result_snippet(content, max_chars=max_chars)
    if isinstance(parsed, dict) and "output" in parsed:
        output = parsed["output"]
        value = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return _format_tool_result_snippet(value, max_chars=max_chars)
    return _format_tool_result_snippet(content, max_chars=max_chars)


def is_invisible_execution(content: str) -> bool:
    if not content.strip():
        return False
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and parsed.get("name") == "bash" and parsed.get("ok") is not True


def render_tool_output(output: str) -> Group:
    view = parse_tool_output(output)
    parts: list[Any] = [Text(view.summary)]
    diff = tool_diff_preview(output)
    if diff:
        parts.append(Syntax(diff.rstrip(), "diff", theme="ansi_dark", word_wrap=False))
    return Group(*parts)


def render_message(
    message: dict[str, Any],
    *,
    project_root: str | None = None,
) -> Any:
    role = _string_or_default(message.get("role"), "message")
    content = _message_content_text(message.get("content"))
    if role == "tool":
        return render_tool_output(content)

    title = ROLE_TITLES.get(role, role.title())
    if role == "assistant":
        return Panel(Text(content), title=title, border_style="green", expand=False)
    if role == "user":
        return Panel(Text(content), title=title, border_style="cyan", expand=False)
    if role == "system":
        label = _system_message_label(content)
        return Panel(Text(content), title=label, border_style="magenta", expand=False)
    params_snippet = build_tool_params_snippet(message.get("function"), project_root=project_root)
    if params_snippet:
        return Panel(Text(params_snippet), title=title, border_style="yellow", expand=False)
    return Panel(Text(content), title=title, border_style="dim", expand=False)


def _tool_diff_text(view: ToolOutputView) -> str | None:
    if view.ok is not True or view.name.lower() not in DIFF_PREVIEW_TOOLS:
        return None
    return view.diff_preview or view.diff


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


def _system_message_label(content: str) -> str:
    normalized = " ".join(content.split()).casefold()
    if "loaded skills" in normalized:
        return "System Skill"
    if "compacted" in normalized or "summary" in normalized:
        return "Summary"
    return "System"


def _format_tool_params_snippet(
    tool_name: str | None,
    args: dict[str, Any],
    *,
    project_root: str | None,
) -> str:
    if tool_name == "bash":
        command = args.get("command")
        description = args.get("description")
        command_text = command.strip() if isinstance(command, str) else ""
        description_text = description.strip() if isinstance(description, str) else ""
        if command_text and description_text:
            return f"{command_text}  # {description_text}"
        return command_text or description_text

    first_key = next(iter(args), "")
    if not first_key:
        return ""
    value = args[first_key]
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if tool_name == "read" and project_root and text.startswith(project_root):
        return text[len(project_root) :].lstrip("/\\")
    return text


def _format_tool_result_snippet(value: str, *, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}... (total {len(value)} chars)"


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
