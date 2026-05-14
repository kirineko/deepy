from __future__ import annotations

import re
from pathlib import Path

import deepy.ui.prompt_input as prompt_input
from deepy.skills import SkillInfo
from deepy.ui.prompt_buffer import PromptBufferState
from deepy.ui.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.prompt_input import PROMPT_MESSAGE
from deepy.ui.prompt_input import PROMPT_PLACEHOLDER
from deepy.ui.prompt_input import PROMPT_TOOLBAR
from deepy.ui.prompt_input import PROMPT_TOOLBAR_BACKGROUND
from deepy.ui.prompt_input import PROMPT_TOOLBAR_FOREGROUND
from deepy.ui.prompt_input import PromptCursorPlacement
from deepy.ui.prompt_input import add_unique_skill
from deepy.ui.prompt_input import build_prompt_key_bindings
from deepy.ui.prompt_input import build_prompt_toolbar
from deepy.ui.prompt_input import character_width
from deepy.ui.prompt_input import create_prompt_session
from deepy.ui.prompt_input import format_selected_skills_status
from deepy.ui.prompt_input import get_prompt_cursor_placement
from deepy.ui.prompt_input import install_shift_enter_key_sequence_overrides
from deepy.ui.prompt_input import install_windows_shift_enter_key_sequence_override
from deepy.ui.prompt_input import is_windows_newline_fallback_enabled
from deepy.ui.prompt_input import is_skill_selected
from deepy.ui.prompt_input import measure_text_position
from deepy.ui.prompt_input import prompt_for_input
from deepy.ui.prompt_input import remove_current_slash_token
from deepy.ui.prompt_input import render_buffer_with_cursor
from deepy.ui.prompt_input import SHIFT_ENTER_SEQUENCES
from deepy.ui.prompt_input import text_width
from deepy.ui.prompt_input import toggle_skill_selection
from deepy.ui.slash_commands import SlashCommandItem


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _skill(name: str, description: str) -> SkillInfo:
    return SkillInfo(name=name, path=Path(f"/skills/{name}/SKILL.md"), description=description)


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
            SlashCommandItem("resume", "resume", "/resume", "Resume"),
        ],
        history_path=tmp_path / "history.txt",
    )

    assert session.multiline is True
    assert session.completer is not None
    assert (tmp_path / "history.txt").exists()


def test_prompt_for_input_uses_styled_prompt_placeholder_and_toolbar():
    class FakePromptSession:
        kwargs = {}

        def prompt(self, message, **kwargs):
            self.message = message
            self.kwargs = kwargs
            return " hello "

    session = FakePromptSession()

    assert prompt_for_input(session) == "hello"
    assert session.message == PROMPT_MESSAGE
    assert session.kwargs["placeholder"] == PROMPT_PLACEHOLDER
    assert session.kwargs["bottom_toolbar"] == PROMPT_TOOLBAR
    assert PROMPT_TOOLBAR_BACKGROUND == "#161821"
    assert PROMPT_TOOLBAR_FOREGROUND == "#a6adc8"


def test_build_prompt_toolbar_only_shows_status():
    status = "model deepseek-v4-pro · thinking max · cwd ~/repo · context 100 / 1,000 (10.0%)"
    toolbar = build_prompt_toolbar(status)

    assert isinstance(toolbar, list)
    assert toolbar == [("class:toolbar.context", status)]


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


def test_prompt_key_bindings_windows_ctrl_j_fallback_inserts_newline(monkeypatch):
    monkeypatch.setattr(prompt_input.sys, "platform", "win32")
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
    ctrl_j = next(binding for binding in bindings.bindings if key_values(binding) == ("c-j",))

    enter.handler(Event())
    ctrl_j.handler(Event())

    assert calls == ["submit", "\n"]


def test_prompt_key_bindings_ctrl_j_fallback_is_windows_only(monkeypatch):
    monkeypatch.setattr(prompt_input.sys, "platform", "darwin")
    bindings = build_prompt_key_bindings()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    assert not any(key_values(binding) == ("c-j",) for binding in bindings.bindings)
    assert is_windows_newline_fallback_enabled("win32")
    assert not is_windows_newline_fallback_enabled("linux")


def test_prompt_key_bindings_ctrl_d_returns_exit_confirmation_when_empty():
    bindings = build_prompt_key_bindings()
    results: list[str] = []

    class Buffer:
        text = ""

        def delete(self):
            results.append("delete")

    class App:
        def exit(self, *, result):
            results.append(result)

    class Event:
        current_buffer = Buffer()
        app = App()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    ctrl_d = next(binding for binding in bindings.bindings if key_values(binding) == ("c-d",))

    ctrl_d.handler(Event())

    assert results == [CTRL_D_EXIT_CONFIRM_SIGNAL]


def test_prompt_key_bindings_ctrl_d_deletes_when_buffer_has_text():
    bindings = build_prompt_key_bindings()
    calls: list[str] = []

    class Buffer:
        text = "hello"

        def delete(self):
            calls.append("delete")

    class App:
        def exit(self, *, result):
            calls.append(result)

    class Event:
        current_buffer = Buffer()
        app = App()

    def key_values(binding):
        return tuple(getattr(key, "value", str(key)) for key in binding.keys)

    ctrl_d = next(binding for binding in bindings.bindings if key_values(binding) == ("c-d",))

    ctrl_d.handler(Event())

    assert calls == ["delete"]


def test_shift_enter_sequences_are_parsed_as_newline_binding_prefix():
    from prompt_toolkit.input.vt100_parser import Vt100Parser

    install_shift_enter_key_sequence_overrides()
    parsed: list[list[tuple[str, str]]] = []

    for sequence in SHIFT_ENTER_SEQUENCES:
        keys: list[tuple[str, str]] = []
        parser = Vt100Parser(lambda key_press: keys.append((str(key_press.key), key_press.data)))
        parser.feed(sequence)
        parser.flush()
        parsed.append(keys)

    assert parsed == [
        [("Keys.Escape", sequence), ("Keys.ControlM", "")]
        for sequence in SHIFT_ENTER_SEQUENCES
    ]


def test_windows_shift_enter_console_input_maps_to_escape_enter():
    from prompt_toolkit.key_binding.key_processor import KeyPress
    from prompt_toolkit.keys import Keys

    class FakeConsoleInputReader:
        SHIFT_PRESSED = 0x0010

        def _event_to_key_presses(self, event):
            return [KeyPress(Keys.ControlM, "\r")]

    class Event:
        def __init__(self, control_key_state: int):
            self.ControlKeyState = control_key_state

    assert install_windows_shift_enter_key_sequence_override(
        platform_name="win32",
        console_input_reader_cls=FakeConsoleInputReader,
    )
    assert install_windows_shift_enter_key_sequence_override(
        platform_name="win32",
        console_input_reader_cls=FakeConsoleInputReader,
    )

    shifted = FakeConsoleInputReader()._event_to_key_presses(Event(0x0010))
    plain = FakeConsoleInputReader()._event_to_key_presses(Event(0))

    assert [key.key for key in shifted] == [Keys.Escape, Keys.ControlM]
    assert [key.key for key in plain] == [Keys.ControlM]


def test_windows_shift_enter_vt100_console_input_yields_supported_sequence():
    class FakeKeyEvent:
        def __init__(self, control_key_state: int, char: str = "\r", key_down: bool = True):
            self.ControlKeyState = control_key_state
            self.KeyDown = key_down
            self.VirtualKeyCode = 13
            self.uChar = type("UChar", (), {"UnicodeChar": char})()

    class FakeEvent:
        def __init__(self, key_event):
            self.KeyEvent = key_event

    class FakeInputRecord:
        EventType = 1

        def __init__(self, key_event):
            self.Event = FakeEvent(key_event)

    class FakeRead:
        def __init__(self, value: int):
            self.value = value

    class FakeVt100ConsoleInputReader:
        def _get_keys(self, read, input_records):
            for record in input_records[: read.value]:
                yield record.Event.KeyEvent.uChar.UnicodeChar

    assert install_windows_shift_enter_key_sequence_override(
        platform_name="win32",
        vt100_console_input_reader_cls=FakeVt100ConsoleInputReader,
        event_types={1: "KeyEvent"},
        key_event_record_cls=FakeKeyEvent,
    )
    assert install_windows_shift_enter_key_sequence_override(
        platform_name="win32",
        vt100_console_input_reader_cls=FakeVt100ConsoleInputReader,
        event_types={1: "KeyEvent"},
        key_event_record_cls=FakeKeyEvent,
    )

    shifted = list(
        FakeVt100ConsoleInputReader()._get_keys(
            FakeRead(1),
            [FakeInputRecord(FakeKeyEvent(0x0010))],
        )
    )
    plain = list(
        FakeVt100ConsoleInputReader()._get_keys(
            FakeRead(1),
            [FakeInputRecord(FakeKeyEvent(0))],
        )
    )

    assert shifted == [SHIFT_ENTER_SEQUENCES[0]]
    assert plain == ["\r"]


def test_windows_shift_enter_patch_is_noop_on_posix_platforms():
    class FakeConsoleInputReader:
        pass

    assert not install_windows_shift_enter_key_sequence_override(
        platform_name="darwin",
        console_input_reader_cls=FakeConsoleInputReader,
    )


def test_text_width_counts_cjk_and_control_characters():
    assert text_width("hello") == 5
    assert text_width("你好") == 4
    assert character_width("\n") == 0
    assert measure_text_position("ab", width=80, initial_column=2).column == 4
