from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.cells import cell_len
from rich.console import Group
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from deepy.todos import normalize_todo_items, todo_counts
from deepy.utils import json as json_utils
from deepy.ui.styles import (
    DARK_PALETTE,
    UiPalette,
    status_style,
)


MAX_SUMMARY_CHARS = 160
MAX_THINKING_SUMMARY_CHARS = 360
MAX_DIFF_LINES = 80
MAX_SYNTAX_SAMPLE_CHARS = 4_000
MAX_SYNTAX_SAMPLE_LINES = 80
DIFF_PREVIEW_TOOLS = {"edit_text", "write_file", "apply_patch"}
SDK_TOOL_ERROR_PREFIX = "An error occurred while running the tool."
SDK_CONTENT_BLOCK_TYPES = {"file", "image", "input_file", "input_image", "input_text", "text"}
SDK_TEXT_BLOCK_TYPES = {"input_text", "text"}
TOOL_DISPLAY_LABELS = {
    "AskUserQuestion": "AskUserQuestion",
    "Search": "Search",
    "WebFetch": "WebFetch",
    "WebSearch": "WebSearch",
    "apply_patch": "Patch",
    "edit_text": "Edit",
    "mcp": "MCP",
    "write_file": "Write",
    "read_file": "Read",
    "shell": "Shell",
    "todo_write": "Todo",
    "load_skill": "Load Skill",
}
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
    old_lineno: int | None = None
    new_lineno: int | None = None


@dataclass(frozen=True)
class DiffPreview:
    path: str | None
    added: int
    removed: int
    lines: list[DiffPreviewLine]
    syntax_path: str | None = None


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


def format_tool_output_summary(output: str) -> str:
    return parse_tool_output(output).summary


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


def format_tool_display_name(name: str) -> str:
    if name in TOOL_DISPLAY_LABELS:
        return TOOL_DISPLAY_LABELS[name]
    stripped = name.strip()
    if not stripped:
        return "Tool"
    return _display_title(stripped)


def format_tool_display_label(name: str) -> str:
    return f"[{format_tool_display_name(name)}]"


def tool_diff_preview(output: str, *, max_lines: int = MAX_DIFF_LINES) -> str | None:
    view = parse_tool_output(output)
    diff = _tool_diff_text(view)
    if not diff:
        return None
    if view.name.lower() in {"write_file", "apply_patch"}:
        return diff
    return _limit_lines(diff, max_lines=max_lines)


def tool_diff_preview_lines(output: str) -> list[DiffPreviewLine]:
    view = parse_tool_output(output)
    diff = _tool_diff_text(view)
    return parse_diff_preview(diff) if diff else []


def render_tool_diff_preview(
    output: str,
    *,
    max_lines: int = MAX_DIFF_LINES,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Group | None:
    palette = palette or DARK_PALETTE
    view = parse_tool_output(output)
    raw_diff = _tool_diff_text(view)
    if not raw_diff:
        return None
    diff = (
        raw_diff
        if view.name.lower() in {"write_file", "apply_patch"}
        else _limit_lines(raw_diff, max_lines=max_lines)
    )
    if not diff:
        return None
    if view.name.lower() == "apply_patch":
        sections = split_diff_preview_sections(diff)
        if not sections:
            return None
        renderables = []
        for index, section in enumerate(sections):
            if index:
                renderables.append(Text(""))
            syntax = _diff_preview_syntax(section, palette)
            renderables.append(render_diff_preview_header(section, tool_name=view.name, palette=palette))
            renderables.extend(
                render_diff_preview_line(line, palette=palette, width=width, syntax=syntax)
                for line in section.lines
            )
        return Group(*renderables)
    preview = parse_diff_preview_view(diff, path=view.path)
    if not preview.lines:
        return None
    syntax = _diff_preview_syntax(preview, palette)
    return Group(
        render_diff_preview_header(preview, tool_name=view.name, palette=palette),
        *(
            render_diff_preview_line(line, palette=palette, width=width, syntax=syntax)
            for line in preview.lines
        ),
    )


def parse_diff_preview_view(diff_preview: str, *, path: str | None = None) -> DiffPreview:
    lines = parse_diff_preview(diff_preview)
    return DiffPreview(
        path=path or _diff_path(diff_preview),
        added=sum(1 for line in lines if line.kind == "added"),
        removed=sum(1 for line in lines if line.kind == "removed"),
        lines=lines,
        syntax_path=_diff_path(diff_preview),
    )


def split_diff_preview_sections(diff_preview: str) -> list[DiffPreview]:
    sections: list[DiffPreview] = []
    for chunk in _split_unified_diff_by_file(diff_preview):
        preview = parse_diff_preview_view(chunk)
        if preview.lines:
            sections.append(preview)
    return sections


def _split_unified_diff_by_file(diff_preview: str) -> list[str]:
    lines = diff_preview.splitlines()
    if not lines:
        return []
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("--- ") and current and any(
            existing.startswith("--- ") for existing in current
        ):
            next_chunk_prefix: list[str] = []
            if current and current[-1].startswith("... "):
                next_chunk_prefix = [current.pop()]
            if current:
                chunks.append(current)
            current = [*next_chunk_prefix, line]
            continue
        current.append(line)
    if current:
        chunks.append(current)
    return ["\n".join(chunk) for chunk in chunks if chunk]


def render_diff_preview_header(
    preview: DiffPreview,
    *,
    tool_name: str,
    palette: UiPalette | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    label = format_tool_display_label(tool_name)
    if preview.path:
        label = f"{label} {preview.path}"
    label = f"{label} (+{preview.added} -{preview.removed})"
    return _tool_label_line(label, style=palette.info, bullet=True)


def render_diff_preview_line(
    line: DiffPreviewLine,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
    syntax: Syntax | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    content = line.content if line.content else " "
    old_lineno = _line_number_text(line.old_lineno)
    new_lineno = _line_number_text(line.new_lineno)
    if line.kind == "added":
        return _pad_changed_diff_line(
            Text.assemble(
                (f"{old_lineno} {new_lineno} ", palette.diff_added_gutter),
                ("+ ", palette.diff_added_marker),
                _highlight_diff_content(content, syntax=syntax, style=palette.diff_added),
            ),
            width=width,
            style=palette.diff_added,
        )
    if line.kind == "removed":
        return _pad_changed_diff_line(
            Text.assemble(
                (f"{old_lineno} {new_lineno} ", palette.diff_removed_gutter),
                ("- ", palette.diff_removed_marker),
                _highlight_diff_content(content, syntax=syntax, style=palette.diff_removed),
            ),
            width=width,
            style=palette.diff_removed,
        )
    return Text.assemble(
        (f"{old_lineno} {new_lineno}   ", palette.diff_context),
        (content, palette.diff_context),
    )


def _pad_changed_diff_line(text: Text, *, width: int | None, style: str) -> Text:
    if width is None or width <= 0:
        return text
    padding = width - cell_len(text.plain)
    if padding > 0:
        text.append(" " * padding, style=style)
    return text


def _diff_preview_syntax(preview: DiffPreview, palette: UiPalette) -> Syntax | None:
    lexer = _guess_diff_preview_lexer(preview)
    if lexer is None:
        return None
    try:
        return Syntax("", lexer, theme=_diff_syntax_theme(palette), line_numbers=False)
    except Exception:
        return None


def _guess_diff_preview_lexer(preview: DiffPreview) -> str | None:
    path = preview.syntax_path or preview.path
    if not path:
        return None
    sample_lines: list[str] = []
    sample_size = 0
    for line in preview.lines:
        if line.kind not in {"added", "removed", "context"} or not line.content.strip():
            continue
        sample_lines.append(line.content)
        sample_size += len(line.content) + 1
        if len(sample_lines) >= MAX_SYNTAX_SAMPLE_LINES or sample_size >= MAX_SYNTAX_SAMPLE_CHARS:
            break
    sample = "\n".join(sample_lines)
    if not sample.strip():
        return None
    try:
        lexer = Syntax.guess_lexer(path, sample)
    except Exception:
        return None
    return lexer if lexer and lexer != "default" else None


def _highlight_diff_content(
    content: str,
    *,
    syntax: Syntax | None,
    style: str,
) -> Text:
    if syntax is None or not content.strip():
        return Text(content, style=style)
    try:
        highlighted = syntax.highlight(content)
    except Exception:
        return Text(content, style=style)

    base = Style.parse(style)
    text = Text(content, style=base)
    for span in highlighted.spans:
        text.stylize(_syntax_style_on_diff_background(span.style, base), span.start, span.end)
    return text


def _diff_syntax_theme(palette: UiPalette) -> str:
    return "default" if palette.name == "light" else "monokai"


def _syntax_style_on_diff_background(style: str | Style, base: Style) -> Style:
    syntax_style = Style.parse(style) if isinstance(style, str) else style
    return Style(
        color=syntax_style.color or base.color,
        bgcolor=base.bgcolor,
        bold=syntax_style.bold,
        italic=syntax_style.italic,
        underline=syntax_style.underline,
        dim=syntax_style.dim,
        strike=syntax_style.strike,
    )


def parse_diff_preview(diff_preview: str) -> list[DiffPreviewLine]:
    lines: list[DiffPreviewLine] = []
    old_lineno: int | None = None
    new_lineno: int | None = None
    for line in diff_preview.splitlines():
        if not line or line.startswith("--- ") or line.startswith("+++ "):
            continue
        hunk = _parse_hunk_header(line)
        if hunk is not None:
            old_lineno, new_lineno = hunk
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+"):
            lines.append(
                DiffPreviewLine(
                    marker="+",
                    content=line[1:],
                    kind="added",
                    old_lineno=None,
                    new_lineno=new_lineno,
                )
            )
            if new_lineno is not None:
                new_lineno += 1
        elif line.startswith("-"):
            lines.append(
                DiffPreviewLine(
                    marker="-",
                    content=line[1:],
                    kind="removed",
                    old_lineno=old_lineno,
                    new_lineno=None,
                )
            )
            if old_lineno is not None:
                old_lineno += 1
        else:
            lines.append(
                DiffPreviewLine(
                    marker=" ",
                    content=line[1:] if line.startswith(" ") else line,
                    kind="context",
                    old_lineno=old_lineno,
                    new_lineno=new_lineno,
                )
            )
            if old_lineno is not None:
                old_lineno += 1
            if new_lineno is not None:
                new_lineno += 1
    return lines


def build_thinking_summary(content: str, message_params: object | None = None) -> str:
    if content:
        normalized = " ".join(content.split())
        result = _truncate(normalized, max_chars=MAX_THINKING_SUMMARY_CHARS)
        if result.endswith((":", "：")):
            result = result[:-1]
        return result

    params = _string_key_dict(message_params)
    if params is not None:
        reasoning_content = params.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            return "(reasoning...)"
    return ""


def build_tool_params_snippet(
    tool_function: object | None, *, project_root: str | None = None
) -> str:
    tool_params = _string_key_dict(tool_function)
    if tool_params is None:
        return ""
    args = tool_params.get("arguments")
    tool_name = tool_params.get("name")
    if not isinstance(args, str) or not args.strip():
        return ""
    try:
        parsed = json_utils.loads(args)
    except json_utils.JSONDecodeError:
        return args.strip()
    parsed_params = _string_key_dict(parsed)
    if parsed_params is None:
        return args.strip()
    return _format_tool_params_snippet(
        tool_name if isinstance(tool_name, str) else None,
        parsed_params,
        project_root=project_root,
    )


def build_tool_result_snippet(content: str, *, max_chars: int = 2_000) -> str:
    trimmed = content.strip()
    if not trimmed:
        return ""
    try:
        parsed = json_utils.loads(content)
    except json_utils.JSONDecodeError:
        return _format_tool_result_snippet(content, max_chars=max_chars)
    if isinstance(parsed, dict) and "output" in parsed:
        output = parsed["output"]
        value = output if isinstance(output, str) else json_utils.dumps(output)
        return _format_tool_result_snippet(value, max_chars=max_chars)
    return _format_tool_result_snippet(content, max_chars=max_chars)


def is_invisible_execution(content: str) -> bool:
    if not content.strip():
        return False
    try:
        parsed = json_utils.loads(content)
    except json_utils.JSONDecodeError:
        return False
    return (
        isinstance(parsed, dict) and parsed.get("name") == "shell" and parsed.get("ok") is not True
    )


def render_tool_output(
    output: str,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Group:
    palette = palette or DARK_PALETTE
    view = parse_tool_output(output)
    parts: list[Any] = [_render_tool_summary(view, palette)]
    todo_board = render_todo_board(output, palette=palette, width=width)
    if todo_board:
        parts.append(todo_board)
    shell_output = render_shell_output_block(output, palette=palette)
    if shell_output:
        parts.append(shell_output)
    diff = render_tool_diff_preview(output, palette=palette, width=width)
    if diff:
        parts.append(diff)
    return Group(*parts)


def render_todo_board(
    output: str,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Panel | None:
    palette = palette or DARK_PALETTE
    view = parse_tool_output(output)
    if not view.metadata or view.metadata.get("kind") != "todo_list":
        return None
    todos, error = normalize_todo_items(view.metadata.get("todos"))
    if error is not None or todos is None or not todos:
        return None
    counts = todo_counts(todos)
    current = next((item for item in todos if item.status == "in_progress"), None)
    if current is None:
        current = next((item for item in todos if item.status == "pending"), None)
    content_width = _todo_content_width(width)
    lines = Text()
    if current is not None:
        lines.append("Current: ", style=f"bold {palette.info}")
        lines.append(_truncate_cells(current.content, content_width), style=palette.info)
        lines.append("\n")
    for item in todos:
        marker, style = _todo_marker_and_style(item.status, palette)
        lines.append(f"{marker} ", style=style)
        text = _truncate_cells(item.content, content_width)
        item_style = f"strike {palette.muted}" if item.status == "completed" else style
        lines.append(text, style=item_style)
        lines.append("\n")
    if lines.plain.endswith("\n"):
        lines.rstrip()
    return Panel(
        lines,
        title=f"Todo List {counts['completed']}/{counts['total']}",
        border_style=palette.panel_border,
        expand=False,
    )


def render_shell_output_block(
    output: str,
    *,
    palette: UiPalette | None = None,
) -> Panel | None:
    palette = palette or DARK_PALETTE
    view = parse_tool_output(output)
    if view.name != "shell" or not view.output:
        return None
    return Panel(
        Text(view.output.rstrip("\n"), style=palette.tool),
        title=format_tool_display_label("shell"),
        border_style=palette.tool,
        expand=False,
    )


def render_message(
    message: dict[str, Any],
    *,
    project_root: str | None = None,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Any:
    palette = palette or DARK_PALETTE
    role = _string_or_default(message.get("role"), "message")
    content = _message_content_text(message.get("content"))
    if role == "tool":
        return render_tool_output(content, palette=palette, width=width)

    title = ROLE_TITLES.get(role, role.title())
    if role == "assistant":
        return Panel(Text(content), title=title, border_style=palette.assistant, expand=False)
    if role == "user":
        return Panel(Text(content), title=title, border_style=palette.user, expand=False)
    if role == "system":
        label = _system_message_label(content)
        return Panel(Text(content), title=label, border_style=palette.system, expand=False)
    params_snippet = build_tool_params_snippet(message.get("function"), project_root=project_root)
    if params_snippet:
        return Panel(Text(params_snippet), title=title, border_style=palette.tool, expand=False)
    return Panel(Text(content), title=title, border_style=palette.muted, expand=False)


def _tool_diff_text(view: ToolOutputView) -> str | None:
    if view.ok is not True or view.name.lower() not in DIFF_PREVIEW_TOOLS:
        return None
    return view.diff_preview or view.diff


def _render_tool_summary(view: ToolOutputView, palette: UiPalette) -> Text:
    style = status_style(view.ok, palette)
    label = format_tool_display_label(view.name)
    if not view.summary.startswith(label):
        return Text(view.summary, style=style)
    return _tool_label_line(view.summary, style=style)


def _tool_label_line(text: str, *, style: str, bullet: bool = False) -> Text:
    label_match = re.match(r"(\[[^\]]+\])(\s?.*)", text, flags=re.DOTALL)
    if not label_match:
        return Text(text, style=style)
    label, detail = label_match.groups()
    parts = []
    if bullet:
        parts.append(("• ", style))
    parts.extend(
        [
            (label, f"bold underline {style}"),
            (detail, style),
        ]
    )
    return Text.assemble(*parts)


def _todo_marker_and_style(status: str, palette: UiPalette) -> tuple[str, str]:
    if status == "completed":
        return "[x]", palette.success
    if status == "in_progress":
        return "[*]", palette.warning
    return "[ ]", palette.muted


def _todo_content_width(width: int | None) -> int:
    if width is None or width <= 0:
        return 80
    # Account for panel border, padding, marker, and a small safety margin.
    return max(16, min(100, width - 12))


def _truncate_cells(text: str, width: int) -> str:
    if width <= 0 or cell_len(text) <= width:
        return text
    suffix = "..."
    available = max(1, width - len(suffix))
    result = ""
    used = 0
    for char in text:
        char_width = cell_len(char)
        if used + char_width > available:
            break
        result += char
        used += char_width
    return result + suffix


def _parse_hunk_header(line: str) -> tuple[int, int] | None:
    match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _diff_path(diff_preview: str) -> str | None:
    for line in diff_preview.splitlines():
        if line.startswith("+++ "):
            return _normalize_diff_path(line[4:].strip())
    for line in diff_preview.splitlines():
        if line.startswith("--- "):
            return _normalize_diff_path(line[4:].strip())
    return None


def _normalize_diff_path(path: str) -> str | None:
    if path == "/dev/null":
        return None
    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]
    return path or None


def _line_number_text(value: int | None) -> str:
    return f"{value:>4}" if value is not None else "    "


def _tool_progress_detail(view: ToolOutputView) -> str:
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
    return json_utils.dumps(content)


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
    if tool_name == "AskUserQuestion":
        return ""

    if tool_name == "todo_write":
        todos = args.get("todos")
        if isinstance(todos, list):
            count = len(todos)
            label = "item" if count == 1 else "items"
            return f"{count} {label}"
        return "read current list"

    if tool_name == "write_file" and "content" in args:
        return _format_write_params_snippet(args, project_root=project_root)
    if tool_name == "apply_patch":
        return _format_patch_params_snippet(args, project_root=project_root)
    if tool_name == "Search":
        return _format_search_params_snippet(args, project_root=project_root)

    if tool_name == "shell":
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
    text = value if isinstance(value, str) else json_utils.dumps(value)
    if tool_name == "read_file":
        return _shorten_project_path(text, project_root=project_root)
    return text


def _format_write_params_snippet(args: dict[str, Any], *, project_root: str | None) -> str:
    path = _string_or_none(args.get("file_path")) or _string_or_none(args.get("path"))
    content = args.get("content")
    path_text = _shorten_project_path(path, project_root=project_root) if path else "file"
    if not isinstance(content, str):
        return path_text
    return f"{path_text} ({_text_size_summary(content)})"


def _format_patch_params_snippet(args: dict[str, Any], *, project_root: str | None) -> str:
    operations = args.get("operations")
    if isinstance(operations, list):
        paths: list[str] = []
        operation_count = 0
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            operation_count += 1
            for key in ("file_path", "destination_path"):
                path = operation.get(key)
                if isinstance(path, str) and path and path not in paths:
                    paths.append(path)
        if not paths:
            label = "operation" if operation_count == 1 else "operations"
            return f"{operation_count} {label}" if operation_count else "operations"
        labels = [_shorten_project_path(path, project_root=project_root) for path in paths]
        file_label = "file" if len(paths) == 1 else "files"
        operation_label = "op" if operation_count == 1 else "ops"
        return f"{operation_count} {operation_label}, {len(paths)} {file_label}: {', '.join(labels)}"

    return "operations"


def _format_search_params_snippet(args: dict[str, Any], *, project_root: str | None) -> str:
    query = _string_or_none(args.get("query")) or "query"
    path = _string_or_none(args.get("path")) or "."
    glob = _string_or_none(args.get("glob"))
    output_mode = _string_or_none(args.get("output_mode"))
    mode = _string_or_none(args.get("mode"))
    shortened_path = _shorten_project_path(path, project_root=project_root)
    parts = [repr(_truncate(query, 60)), "in", shortened_path]
    if glob:
        parts.append(f"glob {glob}")
    if output_mode and output_mode != "content":
        parts.append(output_mode)
    if mode and mode != "literal":
        parts.append(mode)
    return " ".join(parts)


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


def _text_size_summary(text: str) -> str:
    line_count = len(text.splitlines())
    line_label = "line" if line_count == 1 else "lines"
    return f"{line_count:,} {line_label}, {len(text):,} chars"


def _shorten_project_path(path: str, *, project_root: str | None) -> str:
    if project_root and path.startswith(project_root):
        return path[len(project_root) :].lstrip("/\\")
    return path


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
