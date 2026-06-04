from __future__ import annotations

from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from deepy.ui.shared.render.diff_types import (
    MAX_SYNTAX_SAMPLE_CHARS,
    MAX_SYNTAX_SAMPLE_LINES,
    DiffPreview,
    DiffPreviewLine,
)
from deepy.ui.shared.render.styles import UiPalette
from deepy.ui.shared.render.syntax import normalize_syntax_lexer, syntax_style_on_background


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
    return normalize_syntax_lexer(path=path, sample=sample)


def _diff_preview_highlights(preview: DiffPreview, palette: UiPalette) -> dict[int, Text]:
    syntax = _diff_preview_syntax(preview, palette)
    if syntax is None:
        return {}
    highlights: dict[int, Text] = {}
    highlights.update(
        _diff_side_highlights(
            preview.lines,
            syntax=syntax,
            side="old",
            style=palette.diff_removed,
        )
    )
    highlights.update(
        _diff_side_highlights(
            preview.lines,
            syntax=syntax,
            side="new",
            style=palette.diff_added,
        )
    )
    return highlights


def _diff_side_highlights(
    lines: list[DiffPreviewLine],
    *,
    syntax: Syntax,
    side: str,
    style: str,
) -> dict[int, Text]:
    included_kinds = {"removed", "context"} if side == "old" else {"added", "context"}
    parts: list[str] = []
    mapping: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        if line.kind not in included_kinds:
            continue
        mapping.append((index, len(line.content)))
        parts.append(line.content)
    if not parts or not any(part.strip() for part in parts):
        return {}
    try:
        highlighted = syntax.highlight("\n".join(parts))
    except Exception:
        return {}

    offsets: list[int] = []
    offset = 0
    for part in parts:
        offsets.append(offset)
        offset += len(part) + 1

    base = Style.parse(style)
    by_index: dict[int, Text] = {}
    for part_index, (line_index, line_length) in enumerate(mapping):
        line = lines[line_index]
        if line.kind == "context":
            continue
        content = line.content if line.content else " "
        text = Text(content, style=base)
        line_start = offsets[part_index]
        line_end = line_start + line_length
        for span in highlighted.spans:
            start = max(span.start, line_start)
            end = min(span.end, line_end)
            if start < end:
                text.stylize(
                    syntax_style_on_background(span.style, base),
                    start - line_start,
                    end - line_start,
                )
        by_index[line_index] = text
    return by_index


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
        text.stylize(syntax_style_on_background(span.style, base), span.start, span.end)
    return text


def _diff_syntax_theme(palette: UiPalette) -> str:
    return "default" if palette.name == "light" else "monokai"


def _syntax_style_on_diff_background(style: str | Style, base: Style) -> Style:
    return syntax_style_on_background(style, base)
