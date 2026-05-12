from __future__ import annotations

import re
from pathlib import Path

from deepy.skills import SkillInfo
from deepy.ui.prompt_buffer import PromptBufferState
from deepy.ui.prompt_input import IMAGE_ATTACHMENT_CLEAR_HINT
from deepy.ui.prompt_input import PromptCursorPlacement
from deepy.ui.prompt_input import add_unique_skill
from deepy.ui.prompt_input import build_prompt_key_bindings
from deepy.ui.prompt_input import character_width
from deepy.ui.prompt_input import create_prompt_session
from deepy.ui.prompt_input import format_image_attachment_status
from deepy.ui.prompt_input import format_selected_skills_status
from deepy.ui.prompt_input import get_prompt_cursor_placement
from deepy.ui.prompt_input import is_clear_image_attachments_shortcut
from deepy.ui.prompt_input import is_skill_selected
from deepy.ui.prompt_input import measure_text_position
from deepy.ui.prompt_input import remove_current_slash_token
from deepy.ui.prompt_input import render_buffer_with_cursor
from deepy.ui.prompt_input import text_width
from deepy.ui.prompt_input import toggle_skill_selection
from deepy.ui.slash_commands import SlashCommandItem


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _skill(name: str, description: str) -> SkillInfo:
    return SkillInfo(name=name, path=Path(f"/skills/{name}/SKILL.md"), description=description)


def test_format_image_attachment_status_formats_count_label():
    assert format_image_attachment_status(0) == ""
    assert format_image_attachment_status(1) == "📎 1 image attached"
    assert format_image_attachment_status(2) == "📎 2 images attached"
    assert IMAGE_ATTACHMENT_CLEAR_HINT == "ctrl+x clear images"


def test_clear_image_attachments_shortcut_uses_ctrl_x():
    assert is_clear_image_attachments_shortcut("x", ctrl=True)
    assert is_clear_image_attachments_shortcut("X", ctrl=True)
    assert not is_clear_image_attachments_shortcut("x", ctrl=False)
    assert not is_clear_image_attachments_shortcut("c", ctrl=True)


def test_selected_skill_helpers_format_dedupe_toggle_and_clear_slash_tokens():
    skill = _skill("skill-writer", "Write skills")
    other = _skill("code-review", "Review code")

    assert format_selected_skills_status([]) == ""
    assert format_selected_skills_status([skill, other]) == "⚡ skill-writer, code-review"
    assert is_skill_selected([skill], skill)
    assert add_unique_skill([skill], skill) == [skill]
    assert add_unique_skill([skill], other) == [skill, other]
    assert toggle_skill_selection([skill], skill) == []
    assert toggle_skill_selection([skill], other) == [skill, other]
    assert remove_current_slash_token(PromptBufferState("use /skill-writer", 17)) == (
        PromptBufferState("use ", 4)
    )


def test_remove_current_slash_token_ignores_regular_word():
    state = PromptBufferState("use skill-writer", 16)

    assert remove_current_slash_token(state) == state


def test_render_buffer_with_cursor_hides_cursor_when_unfocused():
    assert render_buffer_with_cursor(PromptBufferState("hello", 5), False) == "hello"
    assert render_buffer_with_cursor(PromptBufferState("hello", 1), False) == "hello"
    assert render_buffer_with_cursor(PromptBufferState("hello\n", 6), False) == "hello\n "


def test_render_buffer_with_cursor_draws_cursor_when_focused():
    assert _strip_ansi(render_buffer_with_cursor(PromptBufferState("", 0), True)) == " "
    assert _strip_ansi(render_buffer_with_cursor(PromptBufferState("hello", 5), True)) == "hello "
    assert _strip_ansi(render_buffer_with_cursor(PromptBufferState("hello", 1), True)) == "hello"
    assert _strip_ansi(render_buffer_with_cursor(PromptBufferState("hello\n", 6), True)) == (
        "hello\n "
    )
    assert _strip_ansi(render_buffer_with_cursor(PromptBufferState("\n", 1), True)) == "\n "


def test_render_buffer_with_cursor_shows_placeholder_for_empty_input():
    assert _strip_ansi(render_buffer_with_cursor(PromptBufferState("", 0), True, "Ask Deepy")) == (
        "  Ask Deepy"
    )


def test_get_prompt_cursor_placement_targets_prompt_row_above_footer():
    placement = get_prompt_cursor_placement(PromptBufferState("hello", 5), 80, 2, "Enter send")

    assert placement == PromptCursorPlacement(rows_up=3, column=7)


def test_get_prompt_cursor_placement_targets_reserved_row_after_trailing_newline():
    placement = get_prompt_cursor_placement(PromptBufferState("hello\n", 6), 80, 2, "Enter send")

    assert placement == PromptCursorPlacement(rows_up=3, column=2)


def test_get_prompt_cursor_placement_accounts_for_cjk_width():
    placement = get_prompt_cursor_placement(PromptBufferState("你好", 2), 80, 2, "Enter send")

    assert placement.column == 6


def test_get_prompt_cursor_placement_accounts_for_multiline_buffer_rows():
    end = get_prompt_cursor_placement(PromptBufferState("hello\nworld", 11), 80, 2, "Enter send")
    middle = get_prompt_cursor_placement(PromptBufferState("hello\nworld", 2), 80, 2, "Enter send")

    assert end == PromptCursorPlacement(rows_up=3, column=7)
    assert middle == PromptCursorPlacement(rows_up=4, column=4)


def test_create_prompt_session_configures_history_multiline_and_slash_completion(tmp_path):
    session = create_prompt_session(
        slash_commands=[
            SlashCommandItem("new", "new", "/new", "Start fresh"),
            SlashCommandItem("paste-image", "paste-image", "/paste-image", "Paste image"),
        ],
        history_path=tmp_path / "history.txt",
    )

    assert session.multiline is True
    assert session.completer is not None
    assert (tmp_path / "history.txt").exists()


def test_build_prompt_key_bindings_registers_escape_interrupt():
    bindings = build_prompt_key_bindings(on_interrupt=lambda: None)

    assert any("escape" in binding.keys for binding in bindings.bindings)


def test_prompt_key_bindings_enter_submits_and_escape_enter_inserts_newline():
    bindings = build_prompt_key_bindings()
    calls: list[str] = []

    class Buffer:
        def validate_and_handle(self):
            calls.append("submit")

        def insert_text(self, text: str):
            calls.append(text)

    class Event:
        current_buffer = Buffer()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    enter = next(binding for binding in bindings.bindings if key_values(binding) == ("c-m",))
    escape_enter = next(
        binding for binding in bindings.bindings if key_values(binding) == ("escape", "c-m")
    )

    enter.handler(Event())
    escape_enter.handler(Event())

    assert calls == ["submit", "\n"]


def test_text_width_counts_cjk_and_control_characters():
    assert text_width("hello") == 5
    assert text_width("你好") == 4
    assert character_width("\n") == 0
    assert measure_text_position("ab", width=80, initial_column=2).column == 4
