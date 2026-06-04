from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deepy.todos import normalize_todo_items, todo_counts
from deepy.utils import json as json_utils
from deepy.ui.shared.render.diff_preview import parse_diff_preview
from deepy.ui.shared.render.diff_types import DiffPreviewLine
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette, status_style
from deepy.ui.shared.render.tool_snippets import build_tool_params_snippet
from deepy.ui.shared.render.tool_text import (
    _first_nonempty_line,
    _limit_lines,
    _status_text,
    _string_or_default,
    _string_or_none,
    _truncate,
    format_tool_display_label,
)

MAX_DIFF_LINES = 80
DIFF_PREVIEW_TOOLS = {"update", "write"}
SDK_TOOL_ERROR_PREFIX = "An error occurred while running the tool."
SDK_CONTENT_BLOCK_TYPES = {"file", "image", "input_file", "input_image", "input_text", "text"}
SDK_TEXT_BLOCK_TYPES = {"input_text", "text"}


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
    metadata: dict[str, Any] | None = None
    raw: str = ""


def parse_tool_output(output: str) -> ToolOutputView:
    try:
        payload = json_utils.loads(output)
    except json_utils.JSONDecodeError:
        if error_view := _sdk_tool_error_output(output):
            return error_view
        return _raw_tool_output(output)

    if sdk_view := _sdk_content_tool_output(payload, raw=output):
        return sdk_view

    if not isinstance(payload, dict):
        return _raw_tool_output(output)

    name = _string_or_default(payload.get("name"), "tool")
    ok = payload.get("ok")
    ok_value = ok if isinstance(ok, bool) else None
    status = _status_text(ok_value)
    metadata = payload.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    if _is_retryable_argument_failure(metadata_dict):
        status = "retryable"
    path = _string_or_none(metadata_dict.get("path"))
    diff = _string_or_none(metadata_dict.get("diff"))
    diff_preview = _string_or_none(metadata_dict.get("diff_preview"))
    error = _string_or_none(payload.get("error"))
    text_output = _string_or_default(payload.get("output"), "")
    await_user_response = bool(payload.get("awaitUserResponse"))

    if name == "load_skill" and ok_value is True:
        detail = _string_or_none(metadata_dict.get("name")) or path or ""
    elif name == "Search" and ok_value is True:
        detail = _format_search_output_detail(metadata_dict, text_output)
    elif metadata_dict.get("kind") == "background_task_launch" and ok_value is True:
        detail = _string_or_none(metadata_dict.get("taskId")) or _first_nonempty_line(text_output)
    elif name == "task_list" and ok_value is True:
        detail = _format_background_task_list_detail(metadata_dict, text_output)
    elif name in {"task_output", "task_stop"} and ok_value is True:
        detail = _string_or_none(metadata_dict.get("taskId")) or _first_nonempty_line(text_output)
    elif status == "retryable":
        detail = _string_or_none(metadata_dict.get("recovery")) or error or ""
    elif ok_value is False:
        detail = format_tool_failure_detail(metadata_dict) or error or ""
    else:
        detail = (error or path or _first_nonempty_line(text_output) or "").strip()
    summary = f"{format_tool_display_label(name)} {status}" + (
        f" - {_truncate(detail)}" if detail else ""
    )
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
        metadata=metadata_dict,
        raw=output,
    )


def format_tool_call_summary(
    name: str,
    arguments: str | None,
    *,
    project_root: str | None = None,
) -> str:
    tool_name = name or "tool"
    snippet = build_tool_params_snippet(
        {"name": tool_name, "arguments": arguments or ""},
        project_root=project_root,
    )
    return f"{format_tool_display_label(tool_name)} {snippet}".strip()


def format_tool_progress_summary(
    call_summary: str,
    output: str,
) -> str:
    view = parse_tool_output(output)
    base = call_summary.strip() or format_tool_display_label(view.name)
    detail = _tool_progress_detail(view)
    return f"{base}  {view.status}" + (f" - {detail}" if detail else "")


def tool_status_style(view: ToolOutputView, palette: UiPalette | None = None) -> str:
    palette = palette or DARK_PALETTE
    if view.status == "retryable":
        return palette.warning
    return status_style(view.ok, palette)


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


def _tool_diff_text(view: ToolOutputView) -> str | None:
    if view.ok is not True or view.name.lower() not in DIFF_PREVIEW_TOOLS:
        return None
    return view.diff_preview or view.diff


def should_omit_success_summary(view: ToolOutputView, diff: Any | None) -> bool:
    return view.ok is True and view.name.lower() in DIFF_PREVIEW_TOOLS and diff is not None


def _tool_progress_detail(view: ToolOutputView) -> str:
    if view.status == "retryable" and view.metadata:
        return _truncate(_string_or_none(view.metadata.get("recovery")) or view.error or "")
    if view.ok is False and view.metadata:
        detail = format_tool_failure_detail(view.metadata)
        if detail:
            return _truncate(detail)
    if view.error:
        return _truncate(view.error)
    if view.metadata and view.metadata.get("kind") == "todo_list":
        todos, error = normalize_todo_items(view.metadata.get("todos"))
        if error is None and todos is not None:
            counts = todo_counts(todos)
            current = next((item for item in todos if item.status == "in_progress"), None)
            if current is None:
                current = next((item for item in todos if item.status == "pending"), None)
            suffix = f" - {current.content}" if current is not None else ""
            return _truncate(f"{counts['completed']}/{counts['total']}{suffix}")
    if view.await_user_response:
        return _truncate(_first_nonempty_line(view.output) or "")
    return ""


def format_tool_failure_detail(metadata: dict[str, Any]) -> str:
    failures = metadata.get("failures")
    if not isinstance(failures, list) or not failures:
        return ""
    first = failures[0]
    if not isinstance(first, dict):
        return ""
    error = _string_or_none(first.get("error")) or ""
    code = _string_or_none(first.get("error_code")) or "error"
    index = first.get("index")
    if isinstance(index, int):
        prefix = f"edit #{index + 1} {code}"
    else:
        prefix = code
    return f"{prefix}: {error}" if error else prefix


def _format_search_output_detail(metadata: dict[str, Any], output: str) -> str:
    total_matches = metadata.get("totalMatches")
    matched_files = metadata.get("matchedFileCount")
    total_results = metadata.get("totalResults")
    details: list[str] = []
    if isinstance(total_matches, int):
        match_label = "match" if total_matches == 1 else "matches"
        details.append(f"{total_matches} {match_label}")
    if isinstance(matched_files, int):
        file_label = "file" if matched_files == 1 else "files"
        details.append(f"in {matched_files} {file_label}")
    if isinstance(total_results, int) and total_results != total_matches:
        result_label = "result" if total_results == 1 else "results"
        details.append(f"({total_results} {result_label})")
    if metadata.get("truncated") is True:
        next_offset = metadata.get("nextOffset")
        if isinstance(next_offset, int):
            details.append(f"truncated, offset {next_offset}")
        else:
            details.append("truncated")
    if metadata.get("timedOut") is True:
        details.append("timed out")
    if details:
        return " ".join(details)
    return _first_nonempty_line(output) or ""


def _format_background_task_list_detail(metadata: dict[str, Any], output: str) -> str:
    tasks = metadata.get("tasks")
    if isinstance(tasks, list):
        running = sum(
            1
            for item in tasks
            if isinstance(item, dict) and item.get("status") == "running"
        )
        task_label = "task" if len(tasks) == 1 else "tasks"
        if running:
            running_label = "running" if running == 1 else "running"
            return f"{len(tasks)} {task_label}, {running} {running_label}"
        return f"{len(tasks)} {task_label}"
    return _first_nonempty_line(output) or ""


def _raw_tool_output(output: str) -> ToolOutputView:
    return ToolOutputView(
        name="tool",
        ok=None,
        status="raw",
        summary=_truncate(output),
        raw=output,
    )


def _sdk_tool_error_output(output: str) -> ToolOutputView | None:
    text = output.strip()
    if not text.startswith(SDK_TOOL_ERROR_PREFIX):
        return None
    return ToolOutputView(
        name="tool",
        ok=False,
        status="failed",
        summary=f"{format_tool_display_label('tool')} failed - {_truncate(text)}",
        error=text,
        raw=output,
    )


def _sdk_content_tool_output(payload: Any, *, raw: str) -> ToolOutputView | None:
    is_error = (
        bool(payload.get("isError") or payload.get("is_error"))
        if isinstance(payload, dict)
        else False
    )
    if _is_sdk_content_block(payload):
        content = payload
    else:
        content = payload.get("content") if isinstance(payload, dict) else payload
    content_blocks = _sdk_content_blocks(content)
    structured_content = _sdk_structured_content(payload)
    text = _sdk_content_text(content)
    if text is None and not content_blocks and structured_content is None and not is_error:
        return None
    ok = not is_error
    status = _status_text(ok)
    detail = (
        _first_nonempty_line(text or "")
        or _sdk_non_text_detail(content_blocks, structured_content=structured_content)
        or "MCP tool returned an error"
    )
    return ToolOutputView(
        name="mcp",
        ok=ok,
        status=status,
        summary=f"{format_tool_display_label('mcp')} {status}"
        + (f" - {_truncate(detail)}" if detail else ""),
        output="" if is_error else text or "",
        error=(text or detail) if is_error else None,
        raw=raw,
    )


def _sdk_content_text(content: Any) -> str | None:
    parts: list[str] = []
    for item in _sdk_content_blocks(content):
        text = _sdk_text_block_text(item)
        if text:
            parts.append(text)
    if not parts:
        return None
    return "\n".join(parts)


def _sdk_content_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, dict):
        return [content] if _is_sdk_content_block(content) else []
    if not isinstance(content, list):
        return []
    return [item for item in content if _is_sdk_content_block(item)]


def _sdk_text_block_text(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    block_type = item.get("type")
    text = item.get("text")
    if block_type in SDK_TEXT_BLOCK_TYPES and isinstance(text, str) and text:
        return text
    return None


def _is_sdk_content_block(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    block_type = value.get("type")
    return isinstance(block_type, str) and block_type in SDK_CONTENT_BLOCK_TYPES


def _sdk_structured_content(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    for key in ("structuredContent", "structured_content"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return None


def _sdk_non_text_detail(
    content_blocks: list[dict[str, Any]],
    *,
    structured_content: dict[str, Any] | None,
) -> str:
    if content_blocks:
        count = len(content_blocks)
        label = "content block" if count == 1 else "content blocks"
        return f"{count} {label}"
    if structured_content is not None:
        return "structured content"
    return ""


def _is_retryable_argument_failure(metadata: dict[str, Any]) -> bool:
    return (
        metadata.get("error_code") == "invalid_arguments"
        and metadata.get("retryable") is True
    )
