from __future__ import annotations

from dataclasses import dataclass
from unicodedata import normalize

from deepy.skills import SkillInfo
from deepy.ui.prompt_buffer import PromptBufferState


IMAGE_ATTACHMENT_CLEAR_HINT = "ctrl+x clear images"


@dataclass(frozen=True)
class PromptCursorPlacement:
    rows_up: int
    column: int


def format_image_attachment_status(count: int) -> str:
    if count <= 0:
        return ""
    suffix = "" if count == 1 else "s"
    return f"📎 {count} image{suffix} attached"


def format_selected_skills_status(skills: list[SkillInfo]) -> str:
    names = [skill.name for skill in skills if skill.name]
    if not names:
        return ""
    return f"⚡ {', '.join(names)}"


def is_skill_selected(skills: list[SkillInfo], skill: SkillInfo) -> bool:
    return any(item.name == skill.name for item in skills)


def add_unique_skill(skills: list[SkillInfo], skill: SkillInfo) -> list[SkillInfo]:
    if is_skill_selected(skills, skill):
        return skills
    return [*skills, skill]


def toggle_skill_selection(skills: list[SkillInfo], skill: SkillInfo) -> list[SkillInfo]:
    if is_skill_selected(skills, skill):
        return [item for item in skills if item.name != skill.name]
    return [*skills, skill]


def remove_current_slash_token(state: PromptBufferState) -> PromptBufferState:
    start = state.cursor
    while start > 0 and not state.text[start - 1].isspace():
        start -= 1

    token = state.text[start : state.cursor]
    if not token.startswith("/"):
        return state

    text = f"{state.text[:start]}{state.text[state.cursor:]}"
    return PromptBufferState(text=text, cursor=start)


def is_clear_image_attachments_shortcut(input_text: str, *, ctrl: bool) -> bool:
    return ctrl and input_text in {"x", "X"}


def render_buffer_with_cursor(
    state: PromptBufferState,
    is_focused: bool,
    placeholder: str | None = None,
) -> str:
    text = state.text or ""
    cursor = min(max(state.cursor, 0), len(text))
    before = text[:cursor]
    at = text[cursor] if cursor < len(text) else None
    after = text[cursor + 1 :]

    if not text and placeholder:
        return _dim(f"  {placeholder}")

    if not is_focused:
        return f"{text} " if text.endswith("\n") else text

    if at is None:
        return before + _inverse(" ")
    if at == "\n":
        return before + _inverse(" ") + "\n" + after
    return before + _inverse(at) + after


def get_prompt_cursor_placement(
    state: PromptBufferState,
    screen_width: int,
    prefix_width: int,
    footer_text: str,
) -> PromptCursorPlacement:
    width = max(1, screen_width)
    cursor = min(max(state.cursor, 0), len(state.text))
    before_cursor = state.text[:cursor]
    at = state.text[cursor] if cursor < len(state.text) else None
    display_text = (
        before_cursor
        + (" " if at is None or at == "\n" else at)
        + ("\n" if at == "\n" else "")
        + ("" if at is None else state.text[cursor + 1 :])
    )

    cursor_position = measure_text_position(before_cursor, width=width, initial_column=prefix_width)
    prompt_rows = measure_text_rows(display_text, width=width, initial_column=prefix_width)
    footer_rows = 1 + measure_text_rows(footer_text, width=width, initial_column=0)
    return PromptCursorPlacement(
        rows_up=(prompt_rows - 1 - cursor_position.row) + footer_rows + 1,
        column=cursor_position.column,
    )


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


def _inverse(value: str) -> str:
    return f"\x1b[7m{value}\x1b[0m"


def _dim(value: str) -> str:
    return f"\x1b[2m{value}\x1b[0m"
