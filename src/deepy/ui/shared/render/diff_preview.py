from __future__ import annotations

import re
from typing import Any

from rich.cells import cell_len
from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from deepy.ui.shared.render.diff_highlight import _diff_preview_highlights, _highlight_diff_content
from deepy.ui.shared.render.diff_types import DiffPreview, DiffPreviewLine
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette
from deepy.ui.shared.render.tool_text import (
    _limit_lines,
    _shorten_project_path,
    format_tool_display_label,
)


def render_unified_diff_preview(
    diff: str,
    *,
    tool_name: str,
    path: str | None = None,
    max_lines: int | None = None,
    palette: UiPalette | None = None,
    width: int | None = None,
    project_root: str | None = None,
) -> Group | None:
    palette = palette or DARK_PALETTE
    diff = _limit_lines(diff, max_lines=max_lines) if max_lines is not None else diff
    if not diff:
        return None
    sections = split_diff_preview_sections(diff)
    if len(sections) > 1:
        renderables: list[Any] = []
        for preview in sections:
            highlights = _diff_preview_highlights(preview, palette)
            renderables.append(
                render_diff_preview_header(
                    preview,
                    tool_name=tool_name,
                    palette=palette,
                    project_root=project_root,
                )
            )
            renderables.extend(
                render_diff_preview_line(
                    line,
                    palette=palette,
                    width=width,
                    highlighted_content=highlights.get(index),
                )
                for index, line in enumerate(preview.lines)
            )
        return Group(*renderables)
    preview = sections[0] if sections else parse_diff_preview_view(diff, path=path)
    if not preview.lines:
        return None
    highlights = _diff_preview_highlights(preview, palette)
    return Group(
        render_diff_preview_header(
            preview,
            tool_name=tool_name,
            palette=palette,
            project_root=project_root,
        ),
        *(
            render_diff_preview_line(
                line,
                palette=palette,
                width=width,
                highlighted_content=highlights.get(index),
            )
            for index, line in enumerate(preview.lines)
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
    project_root: str | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    label = format_tool_display_label(tool_name)
    if preview.path:
        label = f"{label} {_shorten_project_path(preview.path, project_root=project_root)}"
    label = f"{label} (+{preview.added} -{preview.removed})"
    return _tool_label_line(label, style=palette.info, bullet=True)


def render_diff_preview_line(
    line: DiffPreviewLine,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
    syntax: Syntax | None = None,
    highlighted_content: Text | None = None,
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
                highlighted_content
                or _highlight_diff_content(content, syntax=syntax, style=palette.diff_added),
            ),
            width=width,
            style=palette.diff_added,
        )
    if line.kind == "removed":
        return _pad_changed_diff_line(
            Text.assemble(
                (f"{old_lineno} {new_lineno} ", palette.diff_removed_gutter),
                ("- ", palette.diff_removed_marker),
                highlighted_content
                or _highlight_diff_content(content, syntax=syntax, style=palette.diff_removed),
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
