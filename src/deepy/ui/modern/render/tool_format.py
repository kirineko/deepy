"""Pure formatting helpers for Modern UI tool/transcript blocks.

Extracted from ``deepy.ui.modern.widgets`` to keep the widget module focused on the
Textual widget classes. These functions are side-effect free string/Text
builders shared by ``ToolBlock``, ``LocalCommandBlock`` and ``QuestionBlock``.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from deepy.todos import normalize_todo_items
from deepy.ui.shared.input.ask_user_question import AskUserQuestionOptionEntry
from deepy.ui.shared.render.message_view import (
    ToolOutputView,
    build_tool_params_snippet,
    format_tool_display_name,
    format_tool_failure_detail,
)
from deepy.utils import json as json_utils


def _tool_output_title(
    view: ToolOutputView,
    *,
    project_root: Path | None = None,
    fallback_command: str = "",
) -> str:
    detail = view.path or ""
    if view.name == "load_skill" and view.metadata:
        detail = str(view.metadata.get("name") or detail)
    if view.name == "shell":
        metadata = view.metadata or {}
        command = metadata.get("command")
        detail = command.strip() if isinstance(command, str) else detail
        if not detail:
            detail = fallback_command.strip()
    if detail and project_root is not None:
        detail = _relative_tool_path(detail, project_root=project_root)
    status = view.status
    name = _tool_title_name(view.name)
    return f"{name} {status}" + (f" - {detail}" if detail else "")


def _relative_tool_path(path: str, *, project_root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve()))
    except (OSError, ValueError):
        return path


def _tool_title_name(name: str) -> str:
    if name.startswith("subagent_"):
        subagent_name = name.removeprefix("subagent_").replace("_", "-")
        return f"Subagent {subagent_name}"
    return format_tool_display_name(name)


def _tool_arguments_body(name: str, arguments: str) -> str:
    if name == "AskUserQuestion":
        return ""
    if not arguments.strip():
        return ""
    if _is_subagent_tool_name(name):
        task = _subagent_input_argument(arguments)
        if task:
            return task
    if name == "shell":
        command = _shell_command_argument(arguments)
        if command:
            return command
    return build_tool_params_snippet({"name": name, "arguments": arguments})


def _shell_command_argument(arguments: str) -> str:
    try:
        args = json_utils.loads(arguments)
    except json_utils.JSONDecodeError:
        return ""
    if not isinstance(args, dict):
        return ""
    command = args.get("command")
    return command.strip() if isinstance(command, str) else ""


def _is_subagent_tool_name(name: str) -> bool:
    return name.startswith("subagent_")


def _subagent_input_argument(arguments: str) -> str:
    try:
        args = json_utils.loads(arguments)
    except json_utils.JSONDecodeError:
        return ""
    if not isinstance(args, dict):
        return ""
    value = args.get("input") or args.get("task") or args.get("prompt")
    return value.strip() if isinstance(value, str) else ""


def _subagent_details(task: str, report: str) -> str:
    parts: list[str] = []
    compact_task = _compact_text(task, max_lines=4, max_chars=500)
    if compact_task:
        parts.extend(["Task", _indent_block(compact_task)])
    compact_report = _compact_text(report, max_lines=16, max_chars=1600)
    if compact_report:
        if parts:
            parts.append("")
        parts.extend(["Report", _indent_block(compact_report)])
    return "\n".join(parts)


def _subagent_parameters(task: str) -> str:
    compact = _compact_text(task, max_lines=4, max_chars=700)
    if not compact:
        return ""
    return "Subagent Parameters\n" + _indent_block(compact)


def _tool_output_body(view: ToolOutputView) -> str:
    if view.name == "AskUserQuestion":
        return "Waiting for user input." if view.await_user_response else _compact_text(view.output or view.summary)
    if view.name == "load_skill" and view.ok is True:
        metadata = view.metadata or {}
        name = str(metadata.get("name") or "skill")
        root = str(metadata.get("root") or metadata.get("path") or "")
        description = str(metadata.get("description") or "").strip()
        lines = [f"Loaded skill: {name}"]
        if description:
            lines.append(f"Description: {description}")
        if root:
            lines.append(f"Root: {root}")
        return "\n".join(lines)
    if view.name == "shell":
        return ""
    if view.name == "read":
        return _read_body(view)
    if view.name == "todo_write":
        return _todo_body(view)
    if view.name in {"WebSearch", "WebFetch"}:
        return _web_body(view)
    if _is_subagent_tool_name(view.name):
        return (view.error or view.output or view.summary).strip()
    if _is_mcp_view(view):
        return _mcp_body(view)
    if view.ok is False and view.metadata:
        detail = format_tool_failure_detail(view.metadata)
        if detail:
            return detail
    return _compact_text(view.error or view.output or view.summary)


def _tool_output_details(view: ToolOutputView) -> str:
    if view.name == "AskUserQuestion":
        return ""
    if view.status == "retryable" and view.metadata:
        recovery = str(view.metadata.get("recovery") or "").strip()
        parse_error = str(view.metadata.get("parse_error") or view.error or "").strip()
        details = "\n".join(line for line in [recovery, parse_error] if line)
        return _compact_text(details, max_lines=8) if details else ""
    text = view.error or view.output or ""
    if not text:
        return ""
    compact = _compact_text(text)
    return "" if compact == text.strip() else text.strip()


def _local_command_title(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    command = str(metadata.get("command") or "").strip()
    status = view.status
    title = f"Shell {status}"
    return f"{title} - {command}" if command else title


def _local_command_output_body(view: ToolOutputView) -> str:
    text = (view.output or "").strip()
    if not text and view.error:
        text = str(view.error).strip()
    if not text:
        return "(no output)"
    return _compact_text(text, max_lines=80)


def _local_command_meta_body(view: ToolOutputView) -> str:
    if view.ok is True:
        return ""
    metadata = view.metadata or {}
    parts: list[str] = []
    exit_code = metadata.get("exit_code", metadata.get("exitCode"))
    if exit_code not in {None, 0}:
        parts.append(f"exit {exit_code}")
    duration = metadata.get("duration_ms", metadata.get("durationMs"))
    if duration is not None:
        parts.append(f"{duration} ms")
    cwd = metadata.get("cwd")
    if cwd:
        parts.append(str(cwd))
    shell_kind = metadata.get("shellKind") or metadata.get("shell_kind")
    if shell_kind:
        parts.append(str(shell_kind))
    if metadata.get("displayOutputTruncated") or metadata.get("captureTruncated"):
        parts.append("truncated")
    return " · ".join(parts)


def _read_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    lines = []
    if view.path:
        lines.append(f"Path: {view.path}")
    if metadata.get("pages"):
        lines.append(f"Pages: {metadata['pages']}")
    if metadata.get("start_line") or metadata.get("startLine"):
        lines.append(f"Start: {metadata.get('start_line', metadata.get('startLine'))}")
    preview = _compact_text(view.error or view.output, max_lines=12, max_chars=1200)
    if preview:
        lines.extend(["", preview] if lines else [preview])
    return "\n".join(lines)


def _todo_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    todos = metadata.get("todos")
    items, error = normalize_todo_items(todos)
    if error is None and items:
        current = next((item for item in items if item.status == "in_progress"), None)
        if current is None:
            current = next((item for item in items if item.status == "pending"), None)
        lines = []
        if current is not None:
            lines.extend(["Current", f"  {_todo_marker(current.status)} {current.id}: {current.content}", ""])
        lines.append("Tasks")
        for item in items[:12]:
            marker = _todo_marker(item.status)
            lines.append(f"  {marker} {item.id}: {item.content}")
        if len(items) > 12:
            lines.append("  ... todos truncated ...")
        return "\n".join(lines)
    return _compact_text(view.error or view.output or view.summary)


def _tool_output_visible(tool_name: str, body: str) -> bool:
    return tool_name == "todo_write" and bool(body.strip())


def _tool_output_renderable(tool_name: str, body: str) -> str | Text:
    if tool_name == "todo_write":
        return _todo_text_renderable(body)
    return body


def _todo_text_renderable(body: str) -> Text:
    text = Text()
    for line_index, line in enumerate(body.splitlines()):
        if line_index:
            text.append("\n")
        stripped = line.strip()
        if stripped in {"Current", "Tasks"}:
            text.append(line, style="bold #7aa2f7")
            continue
        if "[>]" in line:
            text.append(line, style="bold #f9e2af")
            continue
        if "[x]" in line:
            text.append(line, style="#a6e3a1")
            continue
        if "[ ]" in line:
            text.append(line, style="#bac2de")
            continue
        text.append(line)
    return text


def _web_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    lines = []
    preview = _compact_text(view.error or view.output)
    if preview:
        lines.append(preview)
    url = metadata.get("url") or metadata.get("final_url") or metadata.get("finalUrl")
    provider = metadata.get("provider")
    metadata_lines = []
    if provider:
        metadata_lines.append(f"Provider: {provider}")
    if url:
        metadata_lines.append(f"URL: {url}")
    if metadata_lines:
        lines.extend(["", *metadata_lines] if lines else metadata_lines)
    return "\n".join(str(line) for line in lines)


def _is_mcp_view(view: ToolOutputView) -> bool:
    metadata = view.metadata or {}
    return bool(
        metadata.get("mcp_server")
        or metadata.get("server")
        or metadata.get("serverName")
        or metadata.get("mcp_tool")
        or metadata.get("tool")
        or str(metadata.get("kind") or "").startswith("mcp")
    )


def _mcp_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    lines = [f"Status: {view.status}"]
    server = metadata.get("mcp_server") or metadata.get("server") or metadata.get("serverName")
    tool = metadata.get("mcp_tool") or metadata.get("tool")
    state = metadata.get("state") or metadata.get("cleanup") or metadata.get("availability")
    if server:
        lines.append(f"Server: {server}")
    if tool:
        lines.append(f"Tool: {tool}")
    if state:
        lines.append(f"State: {state}")
    preview = _compact_text(view.error or view.output)
    if preview:
        lines.extend(["", preview])
    return "\n".join(str(line) for line in lines)


def _indent_block(text: str) -> str:
    if not text:
        return ""
    return "\n".join(f"  {line}" if line else "" for line in text.splitlines())


def _compact_text(text: str, *, max_lines: int = 8, max_chars: int = 900) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    compact = "\n".join(lines[:max_lines])
    truncated = len(lines) > max_lines
    if len(compact) > max_chars:
        compact = compact[: max_chars - 3].rstrip() + "..."
        truncated = True
    if truncated:
        compact += "\n... output truncated ..."
    return compact


def _todo_marker(status: str) -> str:
    if status == "completed":
        return "[x]"
    if status == "in_progress":
        return "[>]"
    return "[ ]"


def _question_option_label(option: AskUserQuestionOptionEntry, *, selected: bool) -> str:
    marker = "[x]" if selected else "[ ]"
    detail = f" - {option.description}" if option.description else ""
    return f"{marker} {option.label}{detail}"
