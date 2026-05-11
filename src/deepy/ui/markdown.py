from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from rich.text import Text


SegmentKind = Literal["text", "code"]


@dataclass(frozen=True)
class MarkdownSegment:
    kind: SegmentKind
    body: str
    lang: str = ""


def render_markdown(text: str) -> Text:
    output = Text()
    if not text:
        return output

    for segment in split_by_fences(text):
        if segment.kind == "code":
            if segment.lang:
                output.append(f"[{segment.lang}]\n", style="dim")
            output.append(segment.body, style="cyan")
        else:
            output.append(render_inline_block(segment.body))
    return output


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
        fence_match = re.match(r"^\s*```(\w*)\s*$", line)
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


def render_inline_block(text: str) -> Text:
    rendered = Text()
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if index:
            rendered.append("\n")
        rendered.append(render_inline_line(line))
    return rendered


def render_inline_line(line: str) -> Text:
    heading = re.match(r"^(\s*)(#{1,6})\s+(.*)$", line)
    if heading:
        lead, hashes, content = heading.groups()
        rendered = Text(lead)
        rendered.append(hashes, style="dim")
        rendered.append(" ")
        rendered.append(content, style="bold cyan" if len(hashes) > 2 else "bold bright_cyan")
        return rendered

    list_match = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
    if list_match:
        lead, bullet, content = list_match.groups()
        rendered = Text(lead)
        rendered.append(bullet, style="yellow")
        rendered.append(" ")
        rendered.append(render_inline_spans(content))
        return rendered

    number_match = re.match(r"^(\s*)(\d+\.)\s+(.*)$", line)
    if number_match:
        lead, marker, content = number_match.groups()
        rendered = Text(lead)
        rendered.append(marker, style="yellow")
        rendered.append(" ")
        rendered.append(render_inline_spans(content))
        return rendered

    quote = re.match(r"^(\s*)>\s?(.*)$", line)
    if quote:
        lead, content = quote.groups()
        rendered = Text(lead)
        rendered.append("| ", style="dim")
        start = len(rendered)
        rendered.append(render_inline_spans(content))
        rendered.stylize("italic", start, len(rendered))
        return rendered

    return render_inline_spans(line)


def render_inline_spans(text: str) -> Text:
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
            rendered.append(code, style="cyan")
        elif bold is not None:
            rendered.append(bold, style="bold")
        else:
            rendered.append(star_italic or underscore_italic or "", style="italic")
        position = match.end()
    if position < len(text):
        rendered.append(text[position:])
    return rendered
