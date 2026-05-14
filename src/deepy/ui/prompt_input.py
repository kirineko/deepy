from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unicodedata import normalize

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style

from deepy.skills import SkillInfo
from deepy.ui.prompt_buffer import PromptBufferState
from deepy.ui.slash_commands import SlashCommandItem
from deepy.ui.styles import DARK_PALETTE, UiPalette


DEFAULT_PROMPT_HISTORY = Path.home() / ".deepy" / "prompt-history.txt"
CTRL_D_EXIT_CONFIRM_SIGNAL = "\0deepy:ctrl-d-exit-confirm\0"
PROMPT_TOOLBAR_BACKGROUND = "#24283b"
PROMPT_TOOLBAR_FOREGROUND = "#d7def8"
PROMPT_TOOLBAR_HELP = "Enter send · Shift+Enter newline · / commands · Esc interrupt · Ctrl+D twice exit"
PROMPT_MESSAGE: AnyFormattedText = [("class:prompt", "> ")]
PROMPT_PLACEHOLDER: AnyFormattedText = [("class:placeholder", "Type your message...")]
PROMPT_TOOLBAR: AnyFormattedText = [("class:toolbar.help", PROMPT_TOOLBAR_HELP)]
PROMPT_STYLE = None
SHIFT_ENTER_SEQUENCES = (
    "\x1b[27;2;13~",  # xterm modified-key format.
    "\x1b[13;2u",  # Kitty/fixterms CSI-u format, used by modern terminals.
)


@dataclass(frozen=True)
class PromptCursorPlacement:
    rows_up: int
    column: int


def create_prompt_session(
    *,
    slash_commands: list[SlashCommandItem] | None = None,
    history_path: Path | None = None,
    on_interrupt: Callable[[], None] | None = None,
    palette: UiPalette | None = None,
) -> PromptSession[str]:
    install_shift_enter_key_sequence_overrides()
    path = history_path or DEFAULT_PROMPT_HISTORY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    labels = [item.label for item in slash_commands or []]
    return PromptSession(
        history=FileHistory(str(path)),
        completer=WordCompleter(labels, ignore_case=True, sentence=True),
        complete_while_typing=True,
        multiline=True,
        key_bindings=build_prompt_key_bindings(on_interrupt=on_interrupt),
        style=prompt_style(palette),
    )


def build_prompt_key_bindings(
    *,
    on_interrupt: Callable[[], None] | None = None,
) -> KeyBindings:
    install_shift_enter_key_sequence_overrides()
    bindings = KeyBindings()

    @bindings.add("escape")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if on_interrupt is not None:
            on_interrupt()

    @bindings.add("enter")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        event.current_buffer.validate_and_handle()

    @bindings.add("c-d")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if event.current_buffer.text:
            event.current_buffer.delete()
            return
        event.app.exit(result=CTRL_D_EXIT_CONFIRM_SIGNAL)

    @bindings.add("escape", "enter")
    @bindings.add("escape", "c-j")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        event.current_buffer.insert_text("\n")

    return bindings


def install_shift_enter_key_sequence_overrides() -> None:
    from prompt_toolkit.input import vt100_parser
    from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES

    for sequence in SHIFT_ENTER_SEQUENCES:
        ANSI_SEQUENCES[sequence] = (Keys.Escape, Keys.ControlM)
    prefix_cache = getattr(vt100_parser, "_IS_PREFIX_OF_LONGER_MATCH_CACHE", None)
    if hasattr(prefix_cache, "clear"):
        prefix_cache.clear()


def prompt_for_input(
    session: PromptSession[str],
    message: AnyFormattedText | None = None,
    bottom_toolbar: AnyFormattedText | None = None,
) -> str:
    prompt_message = PROMPT_MESSAGE if message is None else message
    return session.prompt(
        prompt_message,
        placeholder=PROMPT_PLACEHOLDER,
        bottom_toolbar=PROMPT_TOOLBAR if bottom_toolbar is None else bottom_toolbar,
    ).strip()


def build_prompt_toolbar(context_status: str = "") -> AnyFormattedText:
    if not context_status:
        return PROMPT_TOOLBAR
    return [
        ("class:toolbar.context", context_status),
        ("class:toolbar.separator", " · "),
        ("class:toolbar.help", PROMPT_TOOLBAR_HELP),
    ]


def prompt_style(palette: UiPalette | None = None) -> Style:
    palette = palette or DARK_PALETTE
    return Style.from_dict(
        {
            "prompt": palette.prompt,
            "placeholder": palette.placeholder,
            "toolbar": f"bg:{palette.toolbar_background} {palette.toolbar_foreground}",
            "toolbar.context": f"bg:{palette.toolbar_background} {palette.toolbar_context}",
            "toolbar.separator": f"bg:{palette.toolbar_background} {palette.toolbar_separator}",
            "toolbar.help": f"bg:{palette.toolbar_background} {palette.toolbar_foreground}",
            "bottom-toolbar": f"bg:{palette.toolbar_background} {palette.toolbar_foreground}",
        }
    )


PROMPT_STYLE = prompt_style()


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
