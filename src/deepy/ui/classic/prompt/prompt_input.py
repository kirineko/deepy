from __future__ import annotations

from pathlib import Path
from typing import Callable, cast

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.completion import Completer, CompleteEvent, Completion, merge_completers
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import AnyFormattedText, StyleAndTextTuples
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.application.run_in_terminal import run_in_terminal
from prompt_toolkit.styles import Style

from deepy.input_suggestions import InputSuggestionController
from deepy.ui.shared.input.file_mentions import FileMentionCompleter
from deepy.ui.shared.input.image_input import ImageAttachmentController, image_attachment_input_text
from deepy.ui.shared.input.slash_commands import (
    SlashCommandItem,
    find_exact_slash_command,
    format_slash_command_completion_label,
    format_slash_command_description,
    rank_slash_commands,
)
from deepy.ui.classic.status.status_footer import StatusFooter
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette
from deepy.ui.classic.prompt.prompt_skills import add_unique_skill as add_unique_skill
from deepy.ui.classic.prompt.prompt_skills import format_selected_skills_status as format_selected_skills_status
from deepy.ui.classic.prompt.prompt_skills import is_skill_selected as is_skill_selected
from deepy.ui.classic.prompt.prompt_skills import toggle_skill_selection as toggle_skill_selection
from deepy.ui.classic.prompt.text_measure import TextPosition as TextPosition
from deepy.ui.classic.prompt.text_measure import character_width as character_width
from deepy.ui.classic.prompt.text_measure import measure_text_position as measure_text_position
from deepy.ui.classic.prompt.text_measure import measure_text_rows as measure_text_rows
from deepy.ui.classic.prompt.text_measure import text_width as text_width


DEFAULT_PROMPT_HISTORY = Path.home() / ".deepy" / "prompt-history.txt"
CTRL_D_EXIT_CONFIRM_SIGNAL = "\0deepy:ctrl-d-exit-confirm\0"
PROMPT_TOOLBAR_BACKGROUND = "#161821"
PROMPT_TOOLBAR_FOREGROUND = "#a6adc8"
PROMPT_TOOLBAR_HELP = "newline: ctrl+j"
PROMPT_MESSAGE: StyleAndTextTuples = [("class:prompt", "> ")]
PROMPT_PLACEHOLDER: StyleAndTextTuples = [("class:placeholder", "Type your message...")]
PROMPT_TOOLBAR: StyleAndTextTuples = [("class:toolbar.help", PROMPT_TOOLBAR_HELP)]


def create_prompt_session(
    *,
    slash_commands: list[SlashCommandItem] | None = None,
    history_path: Path | None = None,
    on_interrupt: Callable[[], None] | None = None,
    on_audit_mode_cycle: Callable[[], None] | None = None,
    input_suggestions: InputSuggestionController | None = None,
    image_attachments: ImageAttachmentController | None = None,
    on_image_paste_notice: Callable[[str], None] | None = None,
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
    session: PromptSession[str] = PromptSession(
        history=FileHistory(str(path)),
        completer=completer,
        complete_while_typing=True,
        multiline=True,
        key_bindings=build_prompt_key_bindings(
            on_interrupt=on_interrupt,
            on_audit_mode_cycle=on_audit_mode_cycle,
            input_suggestions=input_suggestions,
            image_attachments=image_attachments,
            on_image_paste_notice=on_image_paste_notice,
        ),
        auto_suggest=InputSuggestionAutoSuggest(input_suggestions)
        if input_suggestions is not None
        else None,
        style=prompt_style(palette),
    )
    if image_attachments is not None:

        def sync_image_attachments(buffer) -> None:  # pragma: no cover - prompt_toolkit callback
            image_attachments.sync_to_prompt_text(buffer.text)

        session.default_buffer.on_text_changed += sync_image_attachments
    return session


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
    image_attachments: ImageAttachmentController | None = None,
    on_image_paste_notice: Callable[[str], None] | None = None,
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

    def delete_image_attachment_label(event, direction: str) -> bool:
        if image_attachments is None:
            return False
        edit = image_attachments.delete_label_near_cursor(
            event.current_buffer.text,
            event.current_buffer.cursor_position,
            direction="backward" if direction == "backward" else "forward",
        )
        if edit is None:
            return False
        event.current_buffer.text = edit.text
        event.current_buffer.cursor_position = edit.cursor_position
        event.app.invalidate()
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

    @bindings.add("c-v", eager=True)
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if image_attachments is not None:
            result = image_attachments.paste_image_from_clipboard()
            if result.handled:
                if result.attachment is not None:
                    event.current_buffer.insert_text(
                        image_attachment_input_text(
                            result.attachment,
                            text_before_cursor=event.current_buffer.document.text_before_cursor,
                            text_after_cursor=event.current_buffer.document.text_after_cursor,
                        )
                    )
                elif result.notice and on_image_paste_notice is not None:
                    run_in_terminal(lambda: on_image_paste_notice(result.notice))
                event.app.invalidate()
                return
        try:
            clipboard_data = event.app.clipboard.get_data()
        except Exception:
            return
        if clipboard_data.text:
            event.current_buffer.paste_clipboard_data(clipboard_data)
            event.app.invalidate()

    @bindings.add("backspace")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if delete_image_attachment_label(event, "backward"):
            return
        event.current_buffer.delete_before_cursor(count=1)

    @bindings.add("delete")
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        if delete_image_attachment_label(event, "forward"):
            return
        event.current_buffer.delete(count=1)

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


def prompt_toolbar() -> StyleAndTextTuples:
    return PROMPT_TOOLBAR


def prompt_for_input(
    session: PromptSession[str],
    message: AnyFormattedText | None = None,
    bottom_toolbar: AnyFormattedText | None = None,
    input_suggestions: InputSuggestionController | None = None,
    image_attachments: ImageAttachmentController | None = None,
) -> str:
    prompt_message = PROMPT_MESSAGE if message is None else message
    return session.prompt(
        prompt_message,
        placeholder=input_suggestion_placeholder(input_suggestions),
        bottom_toolbar=prompt_toolbar_with_images(bottom_toolbar, image_attachments),
    ).strip()


def prompt_toolbar_with_images(
    bottom_toolbar: AnyFormattedText | None,
    image_attachments: ImageAttachmentController | None,
) -> AnyFormattedText:
    if image_attachments is None:
        return prompt_toolbar() if bottom_toolbar is None else bottom_toolbar

    def resolve() -> AnyFormattedText:
        base = prompt_toolbar() if bottom_toolbar is None else bottom_toolbar
        if callable(base):
            return cast(Callable[[], AnyFormattedText], base)()
        return base

    return resolve


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
) -> AnyFormattedText:
    if isinstance(context_status, StatusFooter):
        return context_status.to_prompt_toolkit(help_text=PROMPT_TOOLBAR_HELP)
    if not context_status:
        return prompt_toolbar()
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


