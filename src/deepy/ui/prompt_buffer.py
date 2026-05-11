from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptBufferState:
    text: str = ""
    cursor: int = 0

    def normalized(self) -> "PromptBufferState":
        return PromptBufferState(self.text, _clamp(self.cursor, 0, len(self.text)))


EMPTY_BUFFER = PromptBufferState()


def insert_text(state: PromptBufferState, value: str) -> PromptBufferState:
    state = state.normalized()
    if not value:
        return state
    text = state.text[: state.cursor] + value + state.text[state.cursor :]
    return PromptBufferState(text, state.cursor + len(value))


def backspace(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    if state.cursor == 0:
        return state
    text = state.text[: state.cursor - 1] + state.text[state.cursor :]
    return PromptBufferState(text, state.cursor - 1)


def delete_forward(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    if state.cursor >= len(state.text):
        return state
    text = state.text[: state.cursor] + state.text[state.cursor + 1 :]
    return PromptBufferState(text, state.cursor)


def move_left(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    return PromptBufferState(state.text, max(state.cursor - 1, 0))


def move_right(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    return PromptBufferState(state.text, min(state.cursor + 1, len(state.text)))


def move_word_left(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    cursor = state.cursor
    while cursor > 0 and state.text[cursor - 1].isspace():
        cursor -= 1
    while cursor > 0 and not state.text[cursor - 1].isspace():
        cursor -= 1
    return PromptBufferState(state.text, cursor)


def move_word_right(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    cursor = state.cursor
    while cursor < len(state.text) and state.text[cursor].isspace():
        cursor += 1
    while cursor < len(state.text) and not state.text[cursor].isspace():
        cursor += 1
    return PromptBufferState(state.text, cursor)


def move_up(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    location = _locate(state)
    if location.line == 0:
        return PromptBufferState(state.text, 0)
    previous_line_end = location.line_start - 1
    previous_line_start = state.text.rfind("\n", 0, previous_line_end) + 1
    previous_line_length = previous_line_end - previous_line_start
    target_column = min(location.column, previous_line_length)
    return PromptBufferState(state.text, previous_line_start + target_column)


def move_down(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    location = _locate(state)
    if location.line_end >= len(state.text):
        return PromptBufferState(state.text, len(state.text))
    next_line_start = location.line_end + 1
    next_line_newline = state.text.find("\n", next_line_start)
    next_line_end = len(state.text) if next_line_newline == -1 else next_line_newline
    next_line_length = next_line_end - next_line_start
    target_column = min(location.column, next_line_length)
    return PromptBufferState(state.text, next_line_start + target_column)


def move_line_start(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    return PromptBufferState(state.text, _locate(state).line_start)


def move_line_end(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    return PromptBufferState(state.text, _locate(state).line_end)


def kill_line(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    line_end = _locate(state).line_end
    if state.cursor >= line_end:
        return state
    text = state.text[: state.cursor] + state.text[line_end:]
    return PromptBufferState(text, state.cursor)


def delete_word_before(state: PromptBufferState) -> PromptBufferState:
    state = state.normalized()
    end = state.cursor
    start = end
    while start > 0 and state.text[start - 1].isspace():
        start -= 1
    while start > 0 and not state.text[start - 1].isspace():
        start -= 1
    if start == end:
        return state
    return PromptBufferState(state.text[:start] + state.text[end:], start)


def reset() -> PromptBufferState:
    return EMPTY_BUFFER


def is_empty(state: PromptBufferState) -> bool:
    return len(state.text) == 0


def get_current_slash_token(state: PromptBufferState) -> str | None:
    state = state.normalized()
    if not state.text:
        return None
    before_cursor = state.text[: state.cursor]
    line_start = before_cursor.rfind("\n") + 1
    line = before_cursor[line_start:]
    if not line.startswith("/"):
        return None
    if re.search(r"\s", line):
        return None
    return line


@dataclass(frozen=True)
class _Location:
    line: int
    column: int
    line_start: int
    line_end: int


def _locate(state: PromptBufferState) -> _Location:
    before = state.text[: state.cursor]
    line_start = before.rfind("\n") + 1
    line = before.count("\n")
    after = state.text[state.cursor :]
    next_newline = after.find("\n")
    line_end = len(state.text) if next_newline == -1 else state.cursor + next_newline
    return _Location(
        line=line,
        column=state.cursor - line_start,
        line_start=line_start,
        line_end=line_end,
    )


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))
