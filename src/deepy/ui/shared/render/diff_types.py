from __future__ import annotations

from dataclasses import dataclass

MAX_SYNTAX_SAMPLE_CHARS = 4_000
MAX_SYNTAX_SAMPLE_LINES = 80


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
