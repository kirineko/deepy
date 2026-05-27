from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from rich.cells import cell_len
from rich.style import StyleType
from rich.syntax import Syntax
from rich.text import Text

from deepy.ui.styles import DARK_PALETTE, UiPalette


SegmentKind = Literal["text", "code"]


@dataclass(frozen=True)
class MarkdownSegment:
    kind: SegmentKind
    body: str
    lang: str = ""


def render_markdown(text: str, *, palette: UiPalette | None = None, width: int | None = None) -> Text:
    palette = palette or DARK_PALETTE
    width = max(24, width or 100)
    output = Text()
    if not text:
        return output

    for segment in split_by_fences(text):
        if segment.kind == "code":
            if output.plain and not output.plain.endswith("\n"):
                output.append("\n")
            output.append(_render_code_block(segment, palette=palette, width=width))
        else:
            output.append(render_inline_block(segment.body, palette=palette, width=width))
    return output


def _render_code_block(
    segment: MarkdownSegment,
    *,
    palette: UiPalette,
    width: int,
) -> Text:
    highlighted = Syntax(
        "",
        segment.lang or "text",
        theme=_syntax_theme_for_palette(palette),
        background_color=_syntax_background_for_palette(palette),
    ).highlight(segment.body)
    lines = highlighted.split("\n", allow_blank=False)
    if not lines:
        lines = [Text("")]

    rendered = Text()
    for index, line in enumerate(lines):
        if index:
            rendered.append("\n")
        rendered.append_text(_code_block_line(line, style=highlighted.style, width=width))
    return rendered


def _code_block_line(line: Text, *, style: StyleType, width: int) -> Text:
    prefix = "  "
    rendered = Text(prefix, style=style)
    rendered.append_text(line)
    padding = " " * max(0, max(cell_len(prefix), width) - cell_len(rendered.plain))
    if padding:
        rendered.append(padding, style=style)
    return rendered


def _syntax_theme_for_palette(palette: UiPalette) -> str:
    return "default" if palette.name == "light" else "monokai"


def _syntax_background_for_palette(palette: UiPalette) -> str:
    return "#e5e7eb" if palette.name == "light" else "#1f2430"


def split_by_fences(text: str) -> list[MarkdownSegment]:
    segments: list[MarkdownSegment] = []
    lines = text.splitlines()
    buffer: list[str] = []
    in_fence = False
    fence_lang = ""
    fence_body: list[str] = []

    def flush_text() -> None:
        nonlocal buffer
        if buffer:
            segments.append(MarkdownSegment(kind="text", body="\n".join(buffer)))
            buffer = []

    for line in lines:
        fence_match = re.match(r"^\s*```([A-Za-z0-9_+.-]*)\s*$", line)
        if fence_match:
            if not in_fence:
                flush_text()
                in_fence = True
                fence_lang = fence_match.group(1) or ""
                fence_body = []
            else:
                segments.append(
                    MarkdownSegment(kind="code", lang=fence_lang, body="\n".join(fence_body))
                )
                in_fence = False
                fence_lang = ""
                fence_body = []
            continue

        if in_fence:
            fence_body.append(line)
        else:
            buffer.append(line)

    if in_fence:
        segments.append(MarkdownSegment(kind="code", lang=fence_lang, body="\n".join(fence_body)))
    else:
        flush_text()
    return segments


def render_inline_block(
    text: str,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    width = max(24, width or 100)
    rendered = Text()
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        table = parse_markdown_table(lines, index)
        if index:
            rendered.append("\n")
        if table is not None:
            table_text, next_index = table
            rendered.append(render_markdown_table(table_text, palette=palette, width=width))
            index = next_index
            continue
        rendered.append(render_inline_line(lines[index], palette=palette, width=width))
        index += 1
    return rendered


def render_inline_line(
    line: str,
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    width = max(24, width or 100)
    heading = re.match(r"^(\s*)(#{1,6})\s+(.*)$", line)
    if heading:
        lead, hashes, content = heading.groups()
        rendered = Text(lead)
        rendered.append(
            content,
            style=palette.markdown_subheading if len(hashes) > 2 else palette.markdown_heading,
        )
        return rendered

    list_match = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
    if list_match:
        lead, _bullet, content = list_match.groups()
        rendered = Text(lead)
        rendered.append("•", style=palette.markdown_bullet)
        rendered.append(" ")
        rendered.append(render_inline_spans(content, palette=palette))
        return rendered

    number_match = re.match(r"^(\s*)(\d+\.)\s+(.*)$", line)
    if number_match:
        lead, marker, content = number_match.groups()
        rendered = Text(lead)
        rendered.append(marker, style=palette.markdown_number)
        rendered.append(" ")
        rendered.append(render_inline_spans(content, palette=palette))
        return rendered

    quote = re.match(r"^(\s*)>\s?(.*)$", line)
    if quote:
        lead, content = quote.groups()
        rendered = Text(lead)
        rendered.append("| ", style=palette.markdown_quote)
        start = len(rendered)
        rendered.append(render_inline_spans(content, palette=palette))
        rendered.stylize("italic", start, len(rendered))
        return rendered

    if re.match(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$", line):
        return Text("─" * min(width, 80), style=palette.markdown_quote)

    return render_inline_spans(line, palette=palette)


def parse_markdown_table(lines: list[str], start: int) -> tuple[list[list[str]], int] | None:
    if start + 1 >= len(lines) or "|" not in lines[start]:
        return None
    header = split_table_row(lines[start])
    separator = split_table_row(lines[start + 1])
    if len(header) < 2 or len(separator) < len(header):
        return None
    if not all(is_table_separator_cell(cell) for cell in separator[: len(header)]):
        return None

    rows = [header[: len(header)]]
    index = start + 2
    while index < len(lines):
        line = lines[index]
        if not line.strip() or "|" not in line:
            break
        cells = split_table_row(line)
        if not cells:
            break
        rows.append(normalize_table_row(cells, len(header)))
        index += 1
    return rows, index


def split_table_row(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", row)]


def is_table_separator_cell(cell: str) -> bool:
    return re.fullmatch(r":?-{3,}:?", cell.strip()) is not None


def normalize_table_row(cells: list[str], columns: int) -> list[str]:
    row = cells[:columns]
    if len(row) < columns:
        row.extend([""] * (columns - len(row)))
    return row


def render_markdown_table(
    rows: list[list[str]],
    *,
    palette: UiPalette | None = None,
    width: int | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    width = max(24, width or 100)
    plain_rows = [[render_inline_spans(cell, palette=palette).plain for cell in row] for row in rows]
    column_widths = table_column_widths(plain_rows, max_width=width)
    rendered = Text()

    append_table_border(rendered, "┌", "┬", "┐", column_widths, style=palette.markdown_quote)
    append_table_row(rendered, plain_rows[0], column_widths, style=palette.markdown_bold, border_style=palette.markdown_quote)
    append_table_border(rendered, "├", "┼", "┤", column_widths, style=palette.markdown_quote)
    for row in plain_rows[1:]:
        append_table_row(rendered, row, column_widths, style="", border_style=palette.markdown_quote)
    append_table_border(rendered, "└", "┴", "┘", column_widths, style=palette.markdown_quote)
    return rendered


def table_column_widths(rows: list[list[str]], *, max_width: int) -> list[int]:
    columns = len(rows[0])
    widths = [
        max(3, max(cell_len(row[index]) for row in rows))
        for index in range(columns)
    ]
    max_table_width = max(24, max_width)
    minimum = 6
    while sum(widths) + (columns * 3) + 1 > max_table_width and max(widths) > minimum:
        largest = max(range(columns), key=lambda index: widths[index])
        widths[largest] -= 1
    return widths


def append_table_border(
    rendered: Text,
    left: str,
    middle: str,
    right: str,
    widths: list[int],
    *,
    style: str,
) -> None:
    rendered.append(left, style=style)
    for index, width in enumerate(widths):
        rendered.append("─" * (width + 2), style=style)
        rendered.append(right if index == len(widths) - 1 else middle, style=style)
    rendered.append("\n")


def append_table_row(
    rendered: Text,
    cells: list[str],
    widths: list[int],
    *,
    style: str,
    border_style: str,
) -> None:
    wrapped = [wrap_cell(cell, width) for cell, width in zip(cells, widths, strict=True)]
    height = max(len(lines) for lines in wrapped)
    for line_index in range(height):
        rendered.append("│", style=border_style)
        for cell_lines, width in zip(wrapped, widths, strict=True):
            value = cell_lines[line_index] if line_index < len(cell_lines) else ""
            rendered.append(" ")
            rendered.append(pad_cell(value, width), style=style)
            rendered.append(" ")
            rendered.append("│", style=border_style)
        rendered.append("\n")


def wrap_cell(text: str, width: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return [""]
    lines: list[str] = []
    current = ""
    for word in normalized.split(" "):
        if not current:
            current = take_word_prefix(word, width)
            remainder = word[len(current) :]
            while remainder:
                lines.append(current)
                current = take_word_prefix(remainder, width)
                remainder = remainder[len(current) :]
            continue
        candidate = f"{current} {word}"
        if cell_len(candidate) <= width:
            current = candidate
            continue
        lines.append(current)
        current = take_word_prefix(word, width)
        remainder = word[len(current) :]
        while remainder:
            lines.append(current)
            current = take_word_prefix(remainder, width)
            remainder = remainder[len(current) :]
    if current:
        lines.append(current)
    return lines or [""]


def take_word_prefix(word: str, width: int) -> str:
    current = ""
    for char in word:
        if current and cell_len(current + char) > width:
            break
        current += char
    return current or word[:1]


def pad_cell(text: str, width: int) -> str:
    return text + (" " * max(0, width - cell_len(text)))


def render_inline_spans(text: str, *, palette: UiPalette | None = None) -> Text:
    palette = palette or DARK_PALETTE
    rendered = Text()
    pattern = re.compile(
        r"`([^`]+)`"
        r"|\*\*([^*]+)\*\*"
        r"|(?<!\*)\*([^*]+)\*(?!\*)"
        r"|_([^_\n]+)_"
    )
    position = 0
    for match in pattern.finditer(text):
        if match.start() > position:
            rendered.append(text[position : match.start()])
        code, bold, star_italic, underscore_italic = match.groups()
        if code is not None:
            rendered.append(code, style=palette.markdown_inline_code)
        elif bold is not None:
            rendered.append(bold, style=palette.markdown_bold)
        else:
            rendered.append(star_italic or underscore_italic or "", style="italic")
        position = match.end()
    if position < len(text):
        rendered.append(text[position:])
    return rendered
