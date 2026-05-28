from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unicodedata import normalize

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.completion import Completer, CompleteEvent, Completion, merge_completers
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import AnyFormattedText, StyleAndTextTuples
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from deepy.input_suggestions import InputSuggestionController
from deepy.skills import SkillInfo
from deepy.ui.file_mentions import FileMentionCompleter
from deepy.ui.prompt_buffer import PromptBufferState
from deepy.ui.slash_commands import (
    SlashCommandItem,
    find_exact_slash_command,
    format_slash_command_completion_label,
    format_slash_command_description,
    rank_slash_commands,
)
from deepy.ui.status_footer import StatusFooter
from deepy.ui.styles import DARK_PALETTE, UiPalette


DEFAULT_PROMPT_HISTORY = Path.home() / ".deepy" / "prompt-history.txt"
CTRL_D_EXIT_CONFIRM_SIGNAL = "\0deepy:ctrl-d-exit-confirm\0"
PROMPT_TOOLBAR_BACKGROUND = "#161821"
PROMPT_TOOLBAR_FOREGROUND = "#a6adc8"
PROMPT_TOOLBAR_HELP = "newline: ctrl+j"
PROMPT_MESSAGE: StyleAndTextTuples = [("class:prompt", "> ")]
PROMPT_PLACEHOLDER: StyleAndTextTuples = [("class:placeholder", "Type your message...")]
PROMPT_TOOLBAR: StyleAndTextTuples = [("class:toolbar.help", PROMPT_TOOLBAR_HELP)]
PROMPT_STYLE = None


@dataclass(frozen=True)
class PromptCursorPlacement:
    rows_up: int
    column: int


def create_prompt_session(
    *,
    slash_commands: list[SlashCommandItem] | None = None,
    history_path: Path | None = None,
    on_interrupt: Callable[[], None] | None = None,
    on_audit_mode_cycle: Callable[[], None] | None = None,
    input_suggestions: InputSuggestionController | None = None,
    palette: UiPalette | None = None,
    project_root: Path | None = None,
) -> PromptSession[str]:
    path = history_path or DEFAULT_PROMPT_HISTORY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    root = project_root or Path.cwd()
    completer = merge_completers(
        [
            SlashCommandCompleter(slash_commands or []),
            FileMentionCompleter(root),
        ],
        deduplicate=True,
    )
    if input_suggestions is not None:
        completer = InputSuggestionAwareCompleter(completer, input_suggestions)
    return PromptSession(
        history=FileHistory(str(path)),
        completer=completer,
        complete_while_typing=True,
        multiline=True,
        key_bindings=build_prompt_key_bindings(
            on_interrupt=on_interrupt,
            on_audit_mode_cycle=on_audit_mode_cycle,
            input_suggestions=input_suggestions,
        ),
        auto_suggest=InputSuggestionAutoSuggest(input_suggestions)
        if input_suggestions is not None
        else None,
        style=prompt_style(palette),
    )


class InputSuggestionAutoSuggest(AutoSuggest):
    def __init__(self, controller: InputSuggestionController | None) -> None:
        self.controller = controller

    def get_suggestion(self, buffer, document: Document) -> Suggestion | None:  # type: ignore[override]
        if self.controller is None:
            return None
        state = self.controller.state
        if document.text:
            self.controller.hide()
            return None
        self.controller.reveal()
        state = self.controller.state
        if not state.visible or not state.text:
            return None
        return Suggestion(state.text)


class InputSuggestionAwareCompleter(Completer):
    def __init__(self, completer: Completer, controller: InputSuggestionController) -> None:
        self.completer = completer
        self.controller = controller

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        state = self.controller.state
        if state.text and not document.text:
            return
        yield from self.completer.get_completions(document, complete_event)


class SlashCommandCompleter(Completer):
    def __init__(self, slash_commands: list[SlashCommandItem]) -> None:
        self.slash_commands = slash_commands

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        del complete_event
        token = _slash_token_before_cursor(document)
        if token is None:
            return
        if find_exact_slash_command(self.slash_commands, token) is not None:
            return
        for item in rank_slash_commands(self.slash_commands, token):
            label = format_slash_command_completion_label(item, token)
            yield Completion(
                label.removesuffix(" *"),
                start_position=-len(token),
                display=label,
                display_meta=format_slash_command_description(item.description),
            )


def _slash_token_before_cursor(document: Document) -> str | None:
    before = document.text_before_cursor
    start = len(before)
    while start > 0 and not before[start - 1].isspace():
        start -= 1
    token = before[start:]
    if not token.startswith("/") or not token:
        return None
    return token


def build_prompt_key_bindings(
    *,
    on_interrupt: Callable[[], None] | None = None,
    on_audit_mode_cycle: Callable[[], None] | None = None,
    input_suggestions: InputSuggestionController | None = None,
) -> KeyBindings:
    bindings = KeyBindings()

    def accept_input_suggestion(event, method: str) -> bool:
        if input_suggestions is None:
            return False
        current_buffer = event.current_buffer
        if current_buffer.text:
            return False
        text = input_suggestions.accept("right" if method == "right" else "tab")
        if text is None:
            return False
        current_buffer.insert_text(text)
        return True

    def apply_current_completion(event) -> bool:
        complete_state = event.current_buffer.complete_state
        if complete_state is None:
            return False
        completion = complete_state.current_completion
        if completion is None and complete_state.completions:
            completion = complete_state.completions[0]
        if completion is not None:
            event.current_buffer.apply_completion(completion)
        else:
            event.current_buffer.cancel_completion()
        return True

    @bindings.add("escape")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if on_interrupt is not None:
            on_interrupt()

    @bindings.add("enter")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if apply_current_completion(event):
            return
        if input_suggestions is not None:
            input_suggestions.dismiss()
        event.current_buffer.validate_and_handle()

    @bindings.add("tab")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if accept_input_suggestion(event, "tab"):
            return
        if apply_current_completion(event):
            return
        event.current_buffer.start_completion(select_first=False)

    @bindings.add("s-tab")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        del event
        if on_audit_mode_cycle is not None:
            on_audit_mode_cycle()

    @bindings.add("right")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if accept_input_suggestion(event, "right"):
            return
        event.current_buffer.cursor_right()

    @bindings.add("c-d")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if event.current_buffer.text:
            if input_suggestions is not None:
                input_suggestions.dismiss()
            event.current_buffer.delete()
            return
        event.app.exit(result=CTRL_D_EXIT_CONFIRM_SIGNAL)

    @bindings.add("c-j")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        event.current_buffer.insert_text("\n")

    return bindings


def prompt_toolbar(platform_name: str | None = None) -> StyleAndTextTuples:
    return PROMPT_TOOLBAR


def prompt_for_input(
    session: PromptSession[str],
    message: AnyFormattedText | None = None,
    bottom_toolbar: AnyFormattedText | None = None,
    input_suggestions: InputSuggestionController | None = None,
) -> str:
    prompt_message = PROMPT_MESSAGE if message is None else message
    return session.prompt(
        prompt_message,
        placeholder=input_suggestion_placeholder(input_suggestions),
        bottom_toolbar=prompt_toolbar() if bottom_toolbar is None else bottom_toolbar,
    ).strip()


def input_suggestion_placeholder(
    input_suggestions: InputSuggestionController | None = None,
) -> StyleAndTextTuples:
    if input_suggestions is None:
        return PROMPT_PLACEHOLDER
    state = input_suggestions.state
    if state.visible and state.text:
        return [("class:auto-suggestion", state.text)]
    return PROMPT_PLACEHOLDER


def build_prompt_toolbar(
    context_status: str | StatusFooter = "",
    *,
    platform_name: str | None = None,
) -> AnyFormattedText:
    if isinstance(context_status, StatusFooter):
        return context_status.to_prompt_toolkit(help_text=PROMPT_TOOLBAR_HELP)
    if not context_status:
        return prompt_toolbar(platform_name)
    return [("class:toolbar.context", context_status)]


def prompt_style(palette: UiPalette | None = None) -> Style:
    palette = palette or DARK_PALETTE
    toolbar_base = f"noreverse bg:{palette.toolbar_background}"
    return Style.from_dict(
        {
            "prompt": palette.prompt,
            "placeholder": palette.placeholder,
            "auto-suggestion": palette.muted,
            "toolbar": f"{toolbar_base} {palette.toolbar_foreground}",
            "toolbar.context": f"{toolbar_base} {palette.toolbar_context}",
            "toolbar.separator": f"{toolbar_base} {palette.toolbar_separator}",
            "toolbar.help": f"{toolbar_base} {palette.toolbar_metadata}",
            "toolbar.title": f"{toolbar_base} {palette.toolbar_identity}",
            "toolbar.identity": f"{toolbar_base} {palette.toolbar_identity}",
            "toolbar.active": f"{toolbar_base} {palette.toolbar_active}",
            "toolbar.loaded": f"{toolbar_base} {palette.toolbar_loaded}",
            "toolbar.metadata": f"{toolbar_base} {palette.toolbar_metadata}",
            "bottom-toolbar": f"{toolbar_base} {palette.toolbar_foreground}",
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
