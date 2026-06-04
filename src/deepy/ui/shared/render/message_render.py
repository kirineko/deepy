from __future__ import annotations

from rich.cells import cell_len
from rich.console import Group
from rich.text import Text

from deepy.todos import normalize_todo_items, todo_counts
from deepy.ui.shared.render.diff_preview import render_unified_diff_preview
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette
from deepy.ui.shared.render.tool_output import MAX_DIFF_LINES, _tool_diff_text, parse_tool_output
from deepy.ui.shared.render.tool_text import _limit_lines


def render_tool_diff_preview(
    output: str,
    *,
    max_lines: int = MAX_DIFF_LINES,
    palette: UiPalette | None = None,
    width: int | None = None,
    project_root: str | None = None,
) -> Group | None:
    palette = palette or DARK_PALETTE
    view = parse_tool_output(output)
    raw_diff = _tool_diff_text(view)
    if not raw_diff:
        return None
    diff = _limit_lines(raw_diff, max_lines=max_lines)
    return render_unified_diff_preview(
        diff,
        tool_name=view.name,
        path=view.path,
        palette=palette,
        width=width,
        project_root=project_root,
    )


def render_todo_board(
    output: str,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Text | None:
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
    content_width = _rail_content_width(width)
    rows: list[tuple[str, str]] = []
    if current is not None:
        rows.append(
            (
                f"Progress {counts['completed']}/{counts['total']} · Current: "
                f"{_truncate_cells(current.content, content_width)}",
                f"bold {palette.info}",
            )
        )
    else:
        rows.append((f"Progress {counts['completed']}/{counts['total']}", f"bold {palette.info}"))
    for item in todos:
        marker, style = _todo_marker_and_style(item.status, palette)
        text = _truncate_cells(item.content, content_width)
        item_style = f"strike {palette.muted}" if item.status == "completed" else style
        rows.append((f"{marker} {text}", item_style))
    return _render_rail_block(
        rows,
        width=width,
        rail_style=palette.panel_border,
        default_style=palette.info,
    )


def render_shell_output_block(
    output: str,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Text | None:
    palette = palette or DARK_PALETTE
    view = parse_tool_output(output)
    if view.name != "shell" or not view.output:
        return None
    return _render_rail_block(
        [(line, palette.tool) for line in view.output.rstrip("\n").splitlines()],
        width=width,
        rail_style=palette.tool,
        default_style=palette.tool,
    )


def _todo_marker_and_style(status: str, palette: UiPalette) -> tuple[str, str]:
    if status == "completed":
        return "[x]", palette.success
    if status == "in_progress":
        return "[*]", palette.warning
    return "[ ]", palette.muted


def _rail_content_width(width: int | None) -> int:
    return max(16, _rail_target_width(width) - cell_len(_rail_prefix()))


def _rail_target_width(width: int | None) -> int:
    if width is None or width <= 0:
        return 88
    return max(20, width)


def _rail_prefix() -> str:
    return "  │ "


def _render_rail_block(
    rows: list[tuple[str, str]],
    *,
    width: int | None,
    rail_style: str,
    default_style: str,
) -> Text:
    target_width = _rail_target_width(width)
    content_width = _rail_content_width(width)
    prefix = _rail_prefix()
    rendered = Text()
    for index, (raw_line, style) in enumerate(rows):
        if index:
            rendered.append("\n")
        line = _truncate_cells(raw_line, content_width)
        line_style = style or default_style
        rendered.append(prefix, style=rail_style)
        rendered.append(line, style=line_style)
        padding = target_width - cell_len(prefix) - cell_len(line)
        if padding > 0:
            rendered.append(" " * padding, style=default_style)
    return rendered


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
