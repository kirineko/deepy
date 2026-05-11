from __future__ import annotations

from deepy.ui.prompt_buffer import (
    EMPTY_BUFFER,
    PromptBufferState,
    backspace,
    delete_forward,
    delete_word_before,
    get_current_slash_token,
    insert_text,
    is_empty,
    kill_line,
    move_down,
    move_left,
    move_line_end,
    move_line_start,
    move_right,
    move_up,
    move_word_left,
    move_word_right,
    reset,
)


def test_insert_text_appends_text_and_advances_cursor():
    next_state = insert_text(EMPTY_BUFFER, "hello")

    assert next_state == PromptBufferState("hello", 5)


def test_backspace_removes_character_before_cursor():
    state = insert_text(EMPTY_BUFFER, "abc")

    assert backspace(state) == PromptBufferState("ab", 2)


def test_backspace_at_start_is_noop():
    assert backspace(PromptBufferState("hi", 0)) == PromptBufferState("hi", 0)


def test_delete_forward_removes_character_after_cursor():
    assert delete_forward(PromptBufferState("hello", 1)) == PromptBufferState("hllo", 1)


def test_move_left_and_right_clamp_boundaries():
    assert move_left(PromptBufferState("hi", 0)).cursor == 0
    assert move_right(PromptBufferState("hi", 2)).cursor == 2


def test_word_movement_skips_whitespace_and_preserves_text():
    state = PromptBufferState("hello  brave world", 18)

    assert move_word_left(state) == PromptBufferState(state.text, 13)
    assert move_word_right(PromptBufferState(state.text, 5)) == PromptBufferState(state.text, 12)


def test_move_up_navigates_to_previous_line_preserving_column():
    assert move_up(PromptBufferState("hello\nworld", 9)).cursor == 3


def test_move_up_from_first_line_moves_to_start():
    assert move_up(PromptBufferState("hello", 3)).cursor == 0


def test_move_down_moves_to_next_line_preserving_column():
    assert move_down(PromptBufferState("hello\nworld", 3)).cursor == 9


def test_move_line_start_and_end_respect_boundaries():
    state = PromptBufferState("first\nsecond line", 9)

    assert move_line_start(state).cursor == 6
    assert move_line_end(state).cursor == len("first\nsecond line")


def test_kill_line_removes_to_end_of_line_only():
    assert kill_line(PromptBufferState("abc\nxyz", 1)) == PromptBufferState("a\nxyz", 1)


def test_delete_word_before_removes_previous_word_and_adjacent_whitespace():
    assert delete_word_before(PromptBufferState("ask the model", 8)) == PromptBufferState(
        "ask model",
        4,
    )


def test_current_slash_token_returns_slash_word_at_cursor():
    assert get_current_slash_token(PromptBufferState("/skill", 6)) == "/skill"


def test_current_slash_token_returns_none_when_token_contains_whitespace():
    assert get_current_slash_token(PromptBufferState("/skill foo", 10)) is None


def test_current_slash_token_supports_new_line():
    assert get_current_slash_token(PromptBufferState("do this\n/n", 10)) == "/n"


def test_current_slash_token_returns_none_without_slash_prefix():
    assert get_current_slash_token(PromptBufferState("hello", 5)) is None


def test_inserting_newlines_builds_multiline_buffer():
    state = insert_text(EMPTY_BUFFER, "abc")
    state = insert_text(state, "\n")
    state = insert_text(state, "def")

    assert state == PromptBufferState("abc\ndef", 7)


def test_reset_and_is_empty():
    assert reset() == EMPTY_BUFFER
    assert is_empty(EMPTY_BUFFER)
    assert not is_empty(PromptBufferState("x", 1))
