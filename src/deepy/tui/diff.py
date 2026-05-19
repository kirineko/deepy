from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group
from rich.text import Text

from deepy.ui.message_view import (
    DiffPreview,
    DiffPreviewLine,
    parse_diff_preview_view,
    parse_tool_output,
    render_diff_preview_header,
    render_diff_preview_line,
)
from deepy.ui.message_view import _diff_preview_syntax as diff_preview_syntax
from deepy.ui.styles import DARK_PALETTE, LIGHT_PALETTE, UiPalette


MAX_RENDERED_DIFF_LINES = 120


@dataclass(frozen=True)
class TuiDiffView:
    tool_name: str
    path: str | None
    added: int
    removed: int
    lines: list[DiffPreviewLine]
    truncated: bool = False
    hunks: tuple[str, ...] = ()


def diff_view_from_tool_output(
    output: str,
    *,
    max_lines: int = MAX_RENDERED_DIFF_LINES,
) -> TuiDiffView | None:
    view = parse_tool_output(output)
    if view.ok is not True or view.name.lower() not in {"write", "modify", "edit"}:
        return None
    raw = view.diff_preview or view.diff
    if not raw:
        return None
    preview = parse_diff_preview_view(raw, path=view.path)
    lines = preview.lines
    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
    return TuiDiffView(
        tool_name=view.name,
        path=preview.path,
        added=preview.added,
        removed=preview.removed,
        lines=lines,
        truncated=truncated,
        hunks=tuple(line for line in raw.splitlines() if line.startswith("@@")),
    )


def render_unified_diff_text(view: TuiDiffView) -> str:
    header_path = view.path or "file"
    lines = [f"{header_path} (+{view.added} -{view.removed})"]
    for line in view.lines:
        old_lineno = _line_number(line.old_lineno)
        new_lineno = _line_number(line.new_lineno)
        marker = line.marker or " "
        lines.append(f"{old_lineno} {new_lineno} {marker} {line.content}")
    if view.truncated:
        lines.append("... diff truncated ...")
    return "\n".join(lines)


def render_unified_diff_rich(
    view: TuiDiffView,
    *,
    theme: str = "dark",
    width: int | None = None,
) -> Group:
    palette = _palette_for_theme(theme)
    preview = DiffPreview(
        path=view.path,
        added=view.added,
        removed=view.removed,
        lines=view.lines,
    )
    syntax = diff_preview_syntax(preview, palette)
    renderables = [
        render_diff_preview_header(preview, tool_name=view.tool_name, palette=palette),
        *(
            _fit_diff_line(
                render_diff_preview_line(line, palette=palette, width=width, syntax=syntax),
                width=width,
            )
            for line in preview.lines
        ),
    ]
    if view.truncated:
        renderables.append(Text("... diff truncated ...", style=palette.diff_context))
    return Group(*renderables)


def _line_number(value: int | None) -> str:
    return "    " if value is None else f"{value:>4}"


def _fit_diff_line(line: Text, *, width: int | None) -> Text:
    if width is None or width <= 0:
        return line
    line.truncate(width, overflow="ellipsis", pad=True)
    return line


def _palette_for_theme(theme: str) -> UiPalette:
    return LIGHT_PALETTE if theme == "light" else DARK_PALETTE
