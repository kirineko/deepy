from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Group
from rich.text import Text

from deepy.ui.shared.render.message_view import (
    DiffPreview,
    DiffPreviewLine,
    _diff_preview_highlights as diff_preview_highlights,
    parse_diff_preview_view,
    parse_tool_output,
    render_diff_preview_header,
    render_diff_preview_line,
    split_diff_preview_sections,
)
from deepy.ui.shared.render.styles import DARK_PALETTE, LIGHT_PALETTE, UiPalette


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
    sections: tuple[DiffPreview, ...] = ()


def diff_view_from_tool_output(
    output: str,
    *,
    max_lines: int = MAX_RENDERED_DIFF_LINES,
    project_root: Path | None = None,
) -> TuiDiffView | None:
    view = parse_tool_output(output)
    if view.ok is not True or view.name.lower() not in {"write", "update"}:
        return None
    raw = view.diff_preview or view.diff
    if not raw:
        return None
    parsed_sections = tuple(split_diff_preview_sections(raw))
    sections, section_truncated = _truncate_diff_sections(
        _relativize_sections(parsed_sections, project_root=project_root),
        max_lines=max_lines,
    )
    preview = _aggregate_diff_sections(
        sections,
        fallback=_relativize_preview(parse_diff_preview_view(raw, path=view.path), project_root=project_root),
    )
    lines = preview.lines
    truncated = section_truncated or len(lines) > max_lines
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
        sections=sections,
    )


def _relativize_sections(
    sections: tuple[DiffPreview, ...],
    *,
    project_root: Path | None,
) -> tuple[DiffPreview, ...]:
    if project_root is None:
        return sections
    return tuple(_relativize_preview(section, project_root=project_root) for section in sections)


def _relativize_preview(preview: DiffPreview, *, project_root: Path | None) -> DiffPreview:
    if project_root is None or not preview.path:
        return preview
    return DiffPreview(
        path=_relative_display_path(preview.path, project_root=project_root),
        added=preview.added,
        removed=preview.removed,
        lines=preview.lines,
        syntax_path=preview.syntax_path,
    )


def _relative_display_path(path: str, *, project_root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve()))
    except (OSError, ValueError):
        return path


def render_unified_diff_text(view: TuiDiffView) -> str:
    if view.sections:
        lines: list[str] = []
        for index, section in enumerate(view.sections):
            if index:
                lines.append("")
            lines.extend(_render_diff_preview_text_lines(section))
        if view.truncated:
            lines.append("... diff truncated ...")
        return "\n".join(lines)
    return "\n".join(_render_diff_preview_text_lines(_view_as_preview(view), truncated=view.truncated))


def _render_diff_preview_text_lines(
    preview: DiffPreview,
    *,
    truncated: bool = False,
) -> list[str]:
    header_path = preview.path or "file"
    lines = [f"{header_path} (+{preview.added} -{preview.removed})"]
    for line in preview.lines:
        old_lineno = _line_number(line.old_lineno)
        new_lineno = _line_number(line.new_lineno)
        marker = line.marker or " "
        lines.append(f"{old_lineno} {new_lineno} {marker} {line.content}")
    if truncated:
        lines.append("... diff truncated ...")
    return lines


def render_unified_diff_rich(
    view: TuiDiffView,
    *,
    theme: str = "dark",
    width: int | None = None,
) -> Group:
    palette = _palette_for_theme(theme)
    if view.sections:
        renderables = []
        for index, preview in enumerate(view.sections):
            if index:
                renderables.append(Text(""))
            highlights = diff_preview_highlights(preview, palette)
            renderables.append(render_diff_preview_header(preview, tool_name=view.tool_name, palette=palette))
            renderables.extend(
                _fit_diff_line(
                    render_diff_preview_line(
                        line,
                        palette=palette,
                        width=width,
                        highlighted_content=highlights.get(line_index),
                    ),
                    width=width,
                )
                for line_index, line in enumerate(preview.lines)
            )
        if view.truncated:
            renderables.append(Text("... diff truncated ...", style=palette.diff_context))
        return Group(*renderables)
    preview = _view_as_preview(view)
    highlights = diff_preview_highlights(preview, palette)
    renderables = [
        render_diff_preview_header(preview, tool_name=view.tool_name, palette=palette),
        *(
            _fit_diff_line(
                render_diff_preview_line(
                    line,
                    palette=palette,
                    width=width,
                    highlighted_content=highlights.get(line_index),
                ),
                width=width,
            )
            for line_index, line in enumerate(preview.lines)
        ),
    ]
    if view.truncated:
        renderables.append(Text("... diff truncated ...", style=palette.diff_context))
    return Group(*renderables)


def _aggregate_diff_sections(sections: tuple[DiffPreview, ...], *, fallback: DiffPreview) -> DiffPreview:
    if not sections:
        return fallback
    lines = [line for section in sections for line in section.lines]
    return DiffPreview(
        path=f"{len(sections)} files" if len(sections) > 1 else sections[0].path,
        added=sum(section.added for section in sections),
        removed=sum(section.removed for section in sections),
        lines=lines,
    )


def _truncate_diff_sections(
    sections: tuple[DiffPreview, ...],
    *,
    max_lines: int,
) -> tuple[tuple[DiffPreview, ...], bool]:
    if not sections:
        return (), False
    remaining = max(0, max_lines)
    truncated = False
    limited: list[DiffPreview] = []
    for section in sections:
        if remaining <= 0:
            truncated = True
            break
        if len(section.lines) > remaining:
            limited.append(
                DiffPreview(
                    path=section.path,
                    added=section.added,
                    removed=section.removed,
                    lines=section.lines[:remaining],
                    syntax_path=section.syntax_path,
                )
            )
            truncated = True
            break
        limited.append(section)
        remaining -= len(section.lines)
    return tuple(limited), truncated


def _view_as_preview(view: TuiDiffView) -> DiffPreview:
    return DiffPreview(
        path=view.path,
        added=view.added,
        removed=view.removed,
        lines=view.lines,
    )


def _line_number(value: int | None) -> str:
    return "    " if value is None else f"{value:>4}"


def _fit_diff_line(line: Text, *, width: int | None) -> Text:
    if width is None or width <= 0:
        return line
    line.truncate(width, overflow="ellipsis", pad=True)
    return line


def _palette_for_theme(theme: str) -> UiPalette:
    return LIGHT_PALETTE if theme == "light" else DARK_PALETTE
