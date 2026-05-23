from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.formatted_text import StyleAndTextTuples
from rich.text import Text

from deepy.ui.styles import DARK_PALETTE, UiPalette


FooterSegmentRole = Literal["identity", "active", "loaded", "metadata", "context"]
FooterPartRole = Literal["title", "loaded", "active", "metadata", "context"]


@dataclass(frozen=True)
class StatusFooterSegment:
    text: str
    role: FooterSegmentRole = "metadata"


@dataclass(frozen=True)
class StatusFooter:
    segments: tuple[StatusFooterSegment, ...]

    @property
    def plain(self) -> str:
        return " · ".join(segment.text for segment in self.segments if segment.text)

    def with_active(self, active_work: str | None) -> "StatusFooter":
        active = (active_work or "").strip()
        if not active:
            return self
        segments = [segment for segment in self.segments if segment.role != "active"]
        insert_at = 1 if segments else 0
        segments.insert(insert_at, StatusFooterSegment(active, "active"))
        return StatusFooter(tuple(segments))

    def to_prompt_toolkit(self, *, help_text: str = "") -> StyleAndTextTuples:
        toolbar: StyleAndTextTuples = []
        for index, segment in enumerate(segment for segment in self.segments if segment.text):
            if index:
                toolbar.append(("class:toolbar.separator", " · "))
            for role, text in _segment_parts(segment):
                toolbar.append((f"class:toolbar.{role}", text))
        if help_text:
            if toolbar:
                toolbar.append(("class:toolbar.separator", " · "))
            for role, text in _help_parts(help_text):
                toolbar.append((f"class:toolbar.{role}", text))
        return toolbar

    def to_rich_text(self, palette: UiPalette | None = None) -> Text:
        palette = palette or DARK_PALETTE
        text = Text()
        for index, segment in enumerate(segment for segment in self.segments if segment.text):
            if index:
                text.append(" · ", style=palette.toolbar_separator)
            for role, value in _segment_parts(segment):
                text.append(value, style=_rich_style_for_role(role, palette))
        return text

    def __str__(self) -> str:
        return self.plain


def _segment_parts(segment: StatusFooterSegment) -> list[tuple[FooterPartRole, str]]:
    if segment.role == "loaded" and segment.text.startswith("[") and segment.text.endswith("]"):
        return [("loaded", segment.text)]
    title = _known_title(segment.text)
    if title is None:
        return [(_part_role_for_segment(segment.role), segment.text)]
    rest = segment.text[len(title) :]
    role = "context" if segment.role == "context" else "metadata"
    return [("title", title), (role, rest)]


def _help_parts(help_text: str) -> list[tuple[FooterPartRole, str]]:
    title = _known_title(help_text)
    if title is None:
        return [("metadata", help_text)]
    return [("title", title), ("metadata", help_text[len(title) :])]


def _known_title(text: str) -> str | None:
    for title in ("provider", "model", "cwd", "mcp", "update", "bg", "ctx", "newline"):
        if text == title or text.startswith(f"{title} ") or text.startswith(f"{title}:"):
            return title
    return None


def _part_role_for_segment(role: FooterSegmentRole) -> FooterPartRole:
    if role == "active":
        return "active"
    if role == "loaded":
        return "loaded"
    if role == "context":
        return "context"
    return "metadata"


def _rich_style_for_role(role: FooterPartRole, palette: UiPalette) -> str:
    if role == "title":
        return _rich_style(palette.toolbar_identity)
    if role == "loaded":
        return _rich_style(palette.toolbar_loaded)
    if role == "active":
        return _rich_style(palette.toolbar_active)
    if role == "context":
        return _rich_style(palette.toolbar_context)
    return _rich_style(palette.toolbar_metadata)


def _rich_style(style: str) -> str:
    if style.endswith(" bold"):
        return f"bold {style.removesuffix(' bold')}"
    return style
