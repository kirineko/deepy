"""Prompt input widgets for the Modern UI.

``PromptTextArea`` and ``PromptPanel`` are mutually dependent (the text area
queries its parent panel and the panel queries the text area), so they live in
one module together with the small ``AttachmentRow`` they coordinate.
"""

from __future__ import annotations

import time
from pathlib import Path

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import OptionList, Static, TextArea
from textual.widgets.option_list import Option

from deepy.llm.multimodal import PromptImageAttachment
from deepy.ui.shared.input.file_mentions import (
    FileMentionDiscovery,
    extract_file_mention_fragment,
    rank_file_mention_candidates,
)
from deepy.ui.shared.input.image_input import ImageAttachmentController
from deepy.ui.shared.input.slash_commands import (
    SlashCommandItem,
    filter_slash_commands,
    format_slash_command_completion_label,
)


class PromptTextArea(TextArea):
    _clear_draft_delete_deadline: float | None = None
    _CLEAR_DRAFT_DELETE_WINDOW_SECONDS = 2.0
    _WHEEL_SCROLL_LINES = 2
    _clock = staticmethod(time.monotonic)

    BINDINGS = [
        Binding("enter", "submit", "Send", priority=True),
        Binding("ctrl+j", "newline", "Newline", priority=True),
        Binding("tab", "accept_suggestion", "Accept suggestion", priority=True, show=False),
        Binding("ctrl+v,super+v", "paste_image", "Paste", priority=True, show=False),
        Binding("ctrl+up", "history_previous", "History previous", priority=True, show=False),
        Binding("ctrl+down", "history_next", "History next", priority=True, show=False),
    ]

    def __init__(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            soft_wrap=True,
            compact=True,
            id=id,
            name=name,
            classes=classes,
            disabled=disabled,
        )

    class Submitted(Message):
        def __init__(
            self,
            text: str,
            image_attachments: list[PromptImageAttachment] | None = None,
        ) -> None:
            self.text = text
            self.image_attachments = list(image_attachments or [])
            super().__init__()

    class SuggestionAccepted(Message):
        pass

    class HistoryPrevious(Message):
        pass

    class HistoryNext(Message):
        pass

    class ImagePasteNotice(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    @on(TextArea.Changed)
    def on_prompt_text_changed(self, event: TextArea.Changed) -> None:
        if self._clear_draft_delete_deadline is not None:
            self._clear_draft_delete_deadline = None

    def prepare_clear_on_next_delete(self) -> None:
        self._clear_draft_delete_deadline = (
            self._clock() + self._CLEAR_DRAFT_DELETE_WINDOW_SECONDS
        )

    def action_delete_left(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel) and panel.remove_selected_image_attachment():
            return
        if self._clear_draft_if_pending():
            return
        super().action_delete_left()

    def action_delete_right(self) -> None:
        if self._clear_draft_if_pending():
            return
        super().action_delete_right()

    def action_submit(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel) and panel.accept_selected_suggestion():
            return
        raw_text = self.text.strip()
        if isinstance(panel, PromptPanel):
            text, image_attachments = panel.collect_image_prompt(raw_text)
        else:
            text = raw_text
            image_attachments = []
        if not text and not image_attachments:
            return
        self.post_message(self.Submitted(text, image_attachments))
        self.clear()
        if isinstance(panel, PromptPanel):
            panel.refresh_image_status()

    def action_newline(self) -> None:
        self.insert("\n")

    def action_accept_suggestion(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel) and panel.accept_selected_suggestion():
            return
        if isinstance(panel, PromptPanel) and panel.accept_input_suggestion():
            return
        self.post_message(self.SuggestionAccepted())

    def action_paste_image(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel) and panel.handle_image_paste():
            return
        paste = getattr(super(), "action_paste", None)
        if callable(paste):
            paste()

    def action_previous_attachment(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel):
            panel.move_image_attachment_selection(-1)

    def action_next_attachment(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel):
            panel.move_image_attachment_selection(1)

    def action_cursor_right(self, select: bool = False) -> None:
        panel = self.parent
        if (
            not select
            and isinstance(panel, PromptPanel)
            and panel.attachment_selection_active
            and panel.move_image_attachment_selection(1)
        ):
            return
        if not select and isinstance(panel, PromptPanel) and panel.accept_input_suggestion():
            return
        super().action_cursor_right(select)

    def action_cursor_left(self, select: bool = False) -> None:
        panel = self.parent
        if (
            not select
            and isinstance(panel, PromptPanel)
            and panel.attachment_selection_active
            and panel.move_image_attachment_selection(-1)
        ):
            return
        super().action_cursor_left(select)

    def action_history_previous(self) -> None:
        self.post_message(self.HistoryPrevious())

    def action_history_next(self) -> None:
        self.post_message(self.HistoryNext())

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self._consume_wheel_event(event, self._WHEEL_SCROLL_LINES)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self._consume_wheel_event(event, -self._WHEEL_SCROLL_LINES)

    def action_cursor_up(self, select: bool = False) -> None:
        panel = self.parent
        if (
            not select
            and isinstance(panel, PromptPanel)
            and panel.attachment_selection_active
            and panel.exit_image_attachment_selection()
        ):
            return
        if not select and isinstance(panel, PromptPanel) and panel.move_suggestion(-1):
            return
        if not select and self.cursor_at_first_line:
            self.action_history_previous()
            return
        super().action_cursor_up(select)

    def action_cursor_down(self, select: bool = False) -> None:
        panel = self.parent
        if not select and isinstance(panel, PromptPanel) and panel.move_suggestion(1):
            return
        if not select and isinstance(panel, PromptPanel) and panel.enter_or_move_image_attachment_selection():
            return
        if not select and self.cursor_at_last_line:
            self.action_history_next()
            return
        super().action_cursor_down(select)

    def _consume_wheel_event(
        self,
        event: events.MouseScrollDown | events.MouseScrollUp,
        y: int,
    ) -> None:
        event.prevent_default()
        event.stop()
        self.scroll_relative(
            y=y * max(1, abs(event.delta_y)),
            animate=False,
            force=True,
            immediate=True,
        )

    def _clear_draft_if_pending(self) -> bool:
        deadline = self._clear_draft_delete_deadline
        if deadline is None:
            return False
        self._clear_draft_delete_deadline = None
        if self._clock() > deadline:
            return False
        if not self.text:
            return False
        self.clear()
        return True


class AttachmentRow(Static, can_focus=True):
    BINDINGS = [
        Binding("left", "previous_attachment", "Previous", show=False),
        Binding("right", "next_attachment", "Next", show=False),
        Binding("backspace", "remove_selected", "Remove", show=False),
        Binding("delete", "remove_selected", "Remove", show=False),
    ]

    class Removed(Message):
        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__("", id=id)
        self.labels: list[str] = []
        self.selected_index = 0
        self.selection_active = False
        self.display = False

    def set_labels(self, labels: list[str], *, selection_active: bool = False) -> None:
        self.labels = list(labels)
        self.selection_active = selection_active
        if not self.labels:
            self.selected_index = 0
            self.selection_active = False
            self.update("")
            self.display = False
            return
        self.selected_index = min(self.selected_index, len(self.labels) - 1)
        self.display = True
        self.update(self._render_labels())

    def action_previous_attachment(self) -> None:
        if not self.labels:
            return
        self.selection_active = True
        self.selected_index = (self.selected_index - 1) % len(self.labels)
        self.update(self._render_labels())

    def action_next_attachment(self) -> None:
        if not self.labels:
            return
        self.selection_active = True
        self.selected_index = (self.selected_index + 1) % len(self.labels)
        self.update(self._render_labels())

    def action_remove_selected(self) -> None:
        if not self.labels:
            return
        self.post_message(self.Removed(self.selected_index))

    def _render_labels(self) -> str:
        parts = []
        for index, label in enumerate(self.labels):
            parts.append(f"▸{label}" if self.selection_active and index == self.selected_index else label)
        return "Attachments  " + "  ".join(parts) + "  · ↓ enter · ←/→ select · ↑ input · Backspace remove"


class PromptPanel(Vertical):
    _INPUT_ROWS = 4

    def __init__(
        self,
        slash_commands: list[SlashCommandItem],
        project_root: Path,
        *,
        image_attachments: ImageAttachmentController | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.slash_commands = slash_commands
        self.discovery = FileMentionDiscovery(project_root)
        self.suggestions: list[str] = []
        self.input_suggestion: str | None = None
        self.image_attachments = image_attachments
        self.attachment_selection_active = False

    def compose(self) -> ComposeResult:
        yield PromptTextArea(id="prompt-input")
        yield AttachmentRow(id="prompt-images")
        yield Static("Enter send · Ctrl+J newline · Tab accept · Esc interrupt", id="prompt-actions")
        yield OptionList(id="prompt-suggestions")

    def on_mount(self) -> None:
        self._sync_prompt_height()

    @on(TextArea.Changed, "#prompt-input")
    def on_prompt_changed(self, event: TextArea.Changed) -> None:
        if self.attachment_selection_active:
            self.attachment_selection_active = False
            self.refresh_image_status()
        self._sync_prompt_height()
        self.refresh_suggestions(event.text_area.text)

    def _sync_prompt_height(self) -> None:
        prompt = self.query_one("#prompt-input", PromptTextArea)
        prompt.styles.height = self._INPUT_ROWS

    def refresh_suggestions(self, text: str) -> None:
        suggestions = self._suggestions_for_text(text)
        self.suggestions = suggestions
        option_list = self.query_one("#prompt-suggestions", OptionList)
        option_list.clear_options()
        if not suggestions:
            option_list.display = False
            option_list.highlighted = None
            self._refresh_input_suggestion_display()
            return
        option_list.display = True
        option_list.add_options([Option(suggestion, id=suggestion) for suggestion in suggestions])
        option_list.highlighted = 0
        self._refresh_input_suggestion_display()

    def accept_selected_suggestion(self) -> bool:
        suggestion = self.selected_suggestion()
        if suggestion is None:
            return False
        prompt = self.query_one("#prompt-input", PromptTextArea)
        prompt.text = self._apply_suggestion(prompt.text, suggestion)
        prompt.move_cursor((0, len(prompt.text)))
        self.refresh_suggestions(prompt.text)
        return True

    def selected_suggestion(self) -> str | None:
        if not self.suggestions:
            return None
        option_list = self.query_one("#prompt-suggestions", OptionList)
        if not option_list.display or option_list.option_count == 0:
            return None
        index = option_list.highlighted if option_list.highlighted is not None else 0
        return str(option_list.get_option_at_index(index).id or self.suggestions[index])

    def set_input_suggestion(self, suggestion: str | None) -> None:
        self.input_suggestion = suggestion
        self._refresh_input_suggestion_display()

    def clear_input_suggestion(self) -> None:
        self.set_input_suggestion(None)

    def handle_image_paste(self) -> bool:
        if self.image_attachments is None:
            return False
        result = self.image_attachments.paste_image_from_clipboard()
        if result.handled:
            if result.attachment is not None:
                pass
            elif result.notice:
                self.post_message(PromptTextArea.ImagePasteNotice(result.notice))
            self.refresh_image_status()
        return result.handled

    def collect_image_prompt(self, text: str) -> tuple[str, list[PromptImageAttachment]]:
        if self.image_attachments is None:
            return text, []
        attachments = self.image_attachments.collect_and_reset()
        self.refresh_image_status()
        return text, attachments

    @on(AttachmentRow.Removed)
    def on_attachment_removed(self, event: AttachmentRow.Removed) -> None:
        event.stop()
        self.remove_image_attachment(event.index)

    def remove_last_image_attachment(self) -> bool:
        if self.image_attachments is None or not self.image_attachments.attachments:
            return False
        return self.remove_image_attachment(len(self.image_attachments.attachments) - 1)

    def remove_selected_image_attachment(self) -> bool:
        if (
            not self.attachment_selection_active
            or self.image_attachments is None
            or not self.image_attachments.attachments
        ):
            return False
        row = self.query_one("#prompt-images", AttachmentRow)
        return self.remove_image_attachment(row.selected_index)

    def enter_or_move_image_attachment_selection(self) -> bool:
        row = self.query_one("#prompt-images", AttachmentRow)
        if not row.labels:
            return False
        if not self.attachment_selection_active:
            self.attachment_selection_active = True
            row.selected_index = 0
            row.set_labels(row.labels, selection_active=True)
            return True
        return self.move_image_attachment_selection(1)

    def exit_image_attachment_selection(self) -> bool:
        if not self.attachment_selection_active:
            return False
        self.attachment_selection_active = False
        self.refresh_image_status()
        return True

    def move_image_attachment_selection(self, delta: int) -> bool:
        row = self.query_one("#prompt-images", AttachmentRow)
        if not row.labels:
            return False
        self.attachment_selection_active = True
        if delta < 0:
            row.action_previous_attachment()
        else:
            row.action_next_attachment()
        return True

    def remove_image_attachment(self, index: int) -> bool:
        if self.image_attachments is None or not self.image_attachments.attachments:
            return False
        if index < 0 or index >= len(self.image_attachments.attachments):
            return False
        self.image_attachments.attachments.pop(index)
        if not self.image_attachments.attachments:
            self.attachment_selection_active = False
        self.refresh_image_status()
        return True

    def refresh_image_status(self) -> None:
        row = self.query_one("#prompt-images", AttachmentRow)
        labels = (
            [attachment.display_label for attachment in self.image_attachments.attachments]
            if self.image_attachments is not None
            else []
        )
        row.set_labels(labels, selection_active=self.attachment_selection_active)

    def accept_input_suggestion(self) -> bool:
        if not self.input_suggestion:
            return False
        option_list = self.query_one("#prompt-suggestions", OptionList)
        if option_list.display and option_list.option_count > 0:
            return False
        prompt = self.query_one("#prompt-input", PromptTextArea)
        if prompt.text:
            return False
        prompt.text = self.input_suggestion
        prompt.suggestion = ""
        prompt.move_cursor((0, len(prompt.text)))
        self._refresh_input_suggestion_display()
        return True

    def move_suggestion(self, delta: int) -> bool:
        option_list = self.query_one("#prompt-suggestions", OptionList)
        if not option_list.display or option_list.option_count == 0:
            return False
        current = option_list.highlighted if option_list.highlighted is not None else 0
        option_list.highlighted = (current + delta) % option_list.option_count
        option_list.scroll_to_highlight()
        return True

    def _suggestions_for_text(self, text: str) -> list[str]:
        token = text.strip()
        if (
            token.startswith("/")
            and "\n" not in text
            and token == text
            and not any(char.isspace() for char in token)
        ):
            if any(
                item.label == token
                or (item.kind == "skill" and f"/skill:{item.name}" == token)
                for item in self.slash_commands
            ):
                return []
            return [
                f"{format_slash_command_completion_label(item, token)}  {item.description}"
                for item in filter_slash_commands(self.slash_commands, token)
            ]
        mention = extract_file_mention_fragment(text)
        if mention is None:
            return []
        if "/" not in mention.fragment:
            paths = (
                self.discovery.top_level_paths()
                if not mention.fragment
                else self.discovery.deep_paths()
            )
        else:
            paths = self.discovery.deep_paths(mention.fragment.rsplit("/", 1)[0])
        return [f"@{path}" for path in rank_file_mention_candidates(paths, mention.fragment)]

    def _apply_suggestion(self, text: str, suggestion: str) -> str:
        value = suggestion.split("  ", 1)[0]
        if value.startswith("/"):
            return value + " "
        mention = extract_file_mention_fragment(text)
        if mention is None:
            return text
        suffix = "" if value.endswith("/") else " "
        return text[: mention.start - 1] + value + suffix

    def _refresh_input_suggestion_display(self) -> None:
        prompt = self.query_one("#prompt-input", PromptTextArea)
        option_list = self.query_one("#prompt-suggestions", OptionList)
        visible = bool(
            self.input_suggestion
            and not prompt.text
            and not (option_list.display and option_list.option_count > 0)
        )
        prompt.suggestion = self.input_suggestion if visible else ""
