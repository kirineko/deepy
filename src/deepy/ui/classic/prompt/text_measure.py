"""Wide-character aware text measurement for the prompt layout.

Extracted from ``deepy.ui.classic.prompt.prompt_input``; ``measure_text_rows`` is used by the
Classic terminal UI and the helpers are re-exported from ``prompt_input`` for
backwards compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from unicodedata import normalize


@dataclass(frozen=True)
class TextPosition:
    row: int
    column: int


def measure_text_rows(text: str, *, width: int, initial_column: int) -> int:
    return measure_text_position(text, width=width, initial_column=initial_column).row + 1


def measure_text_position(text: str, *, width: int, initial_column: int) -> TextPosition:
    effective_width = max(1, width)
    row = 0
    column = min(initial_column, effective_width - 1)

    for char in text:
        if char == "\n":
            row += 1
            column = min(initial_column, effective_width - 1)
            continue

        char_columns = text_width(char)
        if column + char_columns > effective_width:
            row += 1
            column = min(initial_column, effective_width - 1)
        column += char_columns
        if column >= effective_width:
            row += 1
            column = min(initial_column, effective_width - 1)

    return TextPosition(row=row, column=column)


def text_width(value: str) -> int:
    return sum(character_width(char) for char in normalize("NFC", value))


def character_width(char: str) -> int:
    code_point = ord(char)
    if code_point == 0 or code_point < 32 or (0x7F <= code_point < 0xA0):
        return 0
    if 0x300 <= code_point <= 0x36F:
        return 0
    if (
        (0x1100 <= code_point <= 0x115F)
        or (0x2E80 <= code_point <= 0xA4CF)
        or (0xAC00 <= code_point <= 0xD7A3)
        or (0xF900 <= code_point <= 0xFAFF)
        or (0xFE10 <= code_point <= 0xFE19)
        or (0xFE30 <= code_point <= 0xFE6F)
        or (0xFF00 <= code_point <= 0xFF60)
        or (0xFFE0 <= code_point <= 0xFFE6)
    ):
        return 2
    return 1
