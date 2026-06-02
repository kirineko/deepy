from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Markdown, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from deepy.audit import PendingApproval
from deepy.llm.multimodal import PromptImageAttachment
from deepy.tui.diff import TuiDiffView, render_unified_diff_rich, render_unified_diff_text
from deepy.tui.transcript import TranscriptKind, transcript_display
from deepy.todos import normalize_todo_items, todo_counts
from deepy.ui.ask_user_question import (
    AskUserQuestionItem,
    AskUserQuestionOptionEntry,
    OTHER_VALUE,
    build_answer_for_question,
    build_options,
)
from deepy.ui.audit_approval_panel import build_approval_view
from deepy.ui.file_mentions import (
    FileMentionDiscovery,
    extract_file_mention_fragment,
    rank_file_mention_candidates,
)
from deepy.ui.image_input import ImageAttachmentController
from deepy.ui.message_view import (
    ToolOutputView,
    build_tool_params_snippet,
    format_tool_failure_detail,
    format_tool_display_name,
)
from deepy.ui.styles import DARK_PALETTE, UiPalette
from deepy.ui.slash_commands import (
    SlashCommandItem,
    filter_slash_commands,
    format_slash_command_completion_label,
)


class PromptTextArea(TextArea):
    _clear_draft_delete_deadline: float | None = None
    _CLEAR_DRAFT_DELETE_WINDOW_SECONDS = 2.0
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
        if self._delete_image_label("backward"):
            return
        super().action_delete_left()

    def action_delete_right(self) -> None:
        if self._clear_draft_if_pending():
            return
        if self._delete_image_label("forward"):
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

    def _delete_image_label(self, direction: str) -> bool:
        del direction
        return False


class QuestionTextArea(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("ctrl+j", "newline", "Newline", priority=True),
    ]

    class Submitted(Message):
        pass

    def action_submit(self) -> None:
        self.post_message(self.Submitted())

    def action_newline(self) -> None:
        self.insert("\n")


class QuestionOptionList(OptionList):
    def action_cursor_up(self) -> None:
        super().action_cursor_up()
        self._sync_parent_selection()

    def action_cursor_down(self) -> None:
        super().action_cursor_down()
        self._sync_parent_selection()

    def _sync_parent_selection(self) -> None:
        parent = self.parent
        if isinstance(parent, QuestionBlock):
            parent.sync_single_selection_to_highlight()


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
    _MIN_INPUT_ROWS = 1
    _MAX_INPUT_ROWS = 5

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
        self._sync_prompt_height("")

    @on(TextArea.Changed, "#prompt-input")
    def on_prompt_changed(self, event: TextArea.Changed) -> None:
        if self.attachment_selection_active:
            self.attachment_selection_active = False
            self.refresh_image_status()
        self._sync_prompt_height(event.text_area.text)
        self.refresh_suggestions(event.text_area.text)

    def _sync_prompt_height(self, text: str) -> None:
        prompt = self.query_one("#prompt-input", PromptTextArea)
        rows = min(self._MAX_INPUT_ROWS, max(self._MIN_INPUT_ROWS, text.count("\n") + 1))
        prompt.styles.height = rows

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

    def accept_first_suggestion(self) -> bool:
        return self.accept_selected_suggestion()

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

    def remove_selected_or_last_image_attachment(self) -> bool:
        if self.image_attachments is None or not self.image_attachments.attachments:
            return False
        row = self.query_one("#prompt-images", AttachmentRow)
        index = row.selected_index if row.labels else len(self.image_attachments.attachments) - 1
        return self.remove_image_attachment(index)

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


class StatusBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("Deepy Modern UI", id="status-left")
        yield Label("Idle", id="status-right")

    def update_status(self, status: str, context: str | None = None) -> None:
        if context is not None:
            self.query_one("#status-left", Label).update(context)
        self.query_one("#status-right", Label).update(status)


class TranscriptBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("space", "toggle_expand", "Expand", show=False),
    ]

    expanded = reactive(False)

    def __init__(
        self,
        title: str,
        body: str = "",
        *,
        classes: str | None = None,
        kind: TranscriptKind = "info",
    ) -> None:
        self.display_model = transcript_display(kind)
        super().__init__(classes=f"transcript-block {classes or self.display_model.css_class}".strip())
        self.title = title or self.display_model.label
        self.body = body

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="block-title")
        yield Static(self.body, classes="block-body")

    def action_toggle_expand(self) -> None:
        self.expanded = not self.expanded
        if self.expanded:
            self.add_class("-expanded")
        else:
            self.remove_class("-expanded")


class InfoBlock(Vertical, can_focus=True):
    def __init__(self, text: str) -> None:
        self.display_model = transcript_display("info")
        super().__init__(classes="transcript-block info-block")
        self.body = text

    def compose(self) -> ComposeResult:
        yield Static(self.body, classes="block-body")


class UserBlock(TranscriptBlock):
    def __init__(self, text: str) -> None:
        display = transcript_display("user")
        super().__init__(display.label, text, classes=display.css_class, kind="user")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line user-role-line"):
            yield Label(self.title, classes="block-title role-marker user-marker")
            yield Static(self.body, classes="block-body")


class ThinkingBlock(TranscriptBlock):
    def __init__(self, text: str = "") -> None:
        display = transcript_display("reasoning")
        super().__init__(display.label, text, classes=display.css_class, kind="reasoning")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line thinking-role-line"):
            yield Label(self.display_model.label, classes="block-title role-marker thinking-marker")
            yield Static(self.body, classes="block-body thinking-body")

    def update_text(self, text: str) -> None:
        self.body = text
        self.query_one(".block-body", Static).update(text)


class AssistantBlock(Vertical, can_focus=True):
    def __init__(self, markdown: str = "", *, active: bool = False) -> None:
        self.display_model = transcript_display("assistant")
        super().__init__(classes="transcript-block assistant-block")
        self.markdown = markdown
        self.active = active
        if active:
            self.add_class("-active")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line assistant-role-line"):
            yield Label(self._title_text(), classes="block-title role-marker assistant-marker")
            yield Markdown(self.markdown, classes="block-markdown")

    def update_markdown(self, markdown: str) -> None:
        self.markdown = markdown
        self.query_one(Markdown).update(markdown)

    def set_active(self, active: bool) -> None:
        self.active = active
        self.set_class(active, "-active")
        self.query_one(".block-title", Label).update(self._title_text())

    def _title_text(self) -> str:
        return self.display_model.label


class ToolBlock(TranscriptBlock):
    def __init__(
        self,
        label: str,
        body: str = "",
        *,
        call_id: str = "",
        arguments: str = "",
        details: str = "",
        waiting_for_user: bool = False,
        tool_name: str = "",
        retryable: bool = False,
        recovered_from_retry: bool = False,
    ) -> None:
        classes = "tool-block todo-block" if tool_name == "todo_write" else transcript_display("tool").css_class
        if retryable:
            classes += " -retryable"
        super().__init__(label, body, classes=classes, kind="tool")
        self.call_id = call_id
        self.arguments = arguments.strip()
        self.details = details.strip()
        self.output_body = body.strip()
        self.body = ""
        self.waiting_for_user = waiting_for_user
        self.tool_name = tool_name
        self.retryable = retryable
        self.recovered_from_retry = recovered_from_retry
        self.status_state = "retryable" if retryable else "waiting" if waiting_for_user else "running"
        self._sync_status_classes()

    @classmethod
    def from_call(cls, name: str, arguments: str, *, call_id: str) -> ToolBlock:
        display_name = _tool_title_name(name or "tool")
        params = _tool_arguments_body(name or "tool", arguments)
        body = (
            "Waiting for user input."
            if name == "AskUserQuestion"
            else f"Parameters\n  {params}"
            if params
            else "Running"
        )
        return cls(
            f"{display_name} running",
            body,
            call_id=call_id,
            arguments=params,
            tool_name=name or "tool",
        )

    @classmethod
    def from_output(
        cls,
        view: ToolOutputView,
        *,
        call_id: str = "",
        project_root: Path | None = None,
    ) -> ToolBlock:
        body = _tool_output_body(view)
        return cls(
            _tool_output_title(view, project_root=project_root),
            body,
            call_id=call_id,
            details=_tool_output_details(view),
            waiting_for_user=view.await_user_response,
            tool_name=view.name,
            retryable=view.status == "retryable",
        )

    def update_from_call(self, name: str, arguments: str) -> None:
        display_name = _tool_title_name(name or "tool")
        params = _tool_arguments_body(name or "tool", arguments)
        self.tool_name = name or "tool"
        self.arguments = params
        self.title = f"{display_name} running"
        self.output_body = "Running"
        self.body = ""
        self.details = ""
        self.waiting_for_user = False
        self.retryable = False
        self.recovered_from_retry = True
        self.status_state = "running"
        self.query_one(".tool-summary", Static).update(self.title)
        details = self.query_one(".tool-details", Static)
        details.update(self.details)
        details.display = False
        self.set_class(False, "-waiting")
        self.set_class(False, "-retryable")
        self._sync_status_classes()

    def update_from_output(self, view: ToolOutputView, *, project_root: Path | None = None) -> None:
        self.tool_name = view.name
        self.title = _tool_output_title(view, project_root=project_root)
        output_body = _tool_output_body(view)
        self.output_body = output_body
        self.details = _tool_output_details(view)
        self.waiting_for_user = view.await_user_response
        self.retryable = view.status == "retryable"
        self.status_state = "waiting" if self.waiting_for_user else view.status
        self.body = ""
        self.query_one(".tool-summary", Static).update(self.title)
        details = self.query_one(".tool-details", Static)
        details.update(self.details)
        details.display = bool(self.details and self.expanded)
        self.set_class(self.waiting_for_user, "-waiting")
        self.set_class(self.retryable, "-retryable")
        self._sync_status_classes()
        self.set_class(view.name == "todo_write", "todo-block")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line tool-role-line"):
            yield Label(self.display_model.label, classes="block-title role-marker tool-marker")
            yield Static(self.title, classes="block-body tool-summary")
        detail = Static(self.details, classes="tool-details")
        detail.display = False
        yield detail

    def action_toggle_expand(self) -> None:
        super().action_toggle_expand()
        self.query_one(".tool-details", Static).display = False

    def _sync_status_classes(self) -> None:
        self.set_class(self.status_state == "running", "-running")
        self.set_class(self.status_state == "waiting", "-waiting")
        self.set_class(self.status_state == "retryable", "-retryable")
        self.set_class(self.status_state == "ok", "-ok")
        self.set_class(self.status_state == "failed", "-failed")


class LocalCommandBlock(Vertical, can_focus=True):
    def __init__(self, view: ToolOutputView, *, call_id: str = "") -> None:
        self.display_model = transcript_display("tool")
        super().__init__(classes="transcript-block tool-block local-command-block")
        self.call_id = call_id
        self.view = view
        self.title = _local_command_title(view)
        self.output_body = _local_command_output_body(view)
        self.meta_body = _local_command_meta_body(view)
        self.set_class(view.ok is True, "-ok")
        self.set_class(view.ok is False, "-failed")

    @classmethod
    def from_output(cls, view: ToolOutputView, *, call_id: str = "") -> LocalCommandBlock:
        return cls(view, call_id=call_id)

    def compose(self) -> ComposeResult:
        yield Static(self.output_body, classes="block-body local-command-output")
        meta = Static(self.meta_body, classes="tool-details local-command-meta")
        meta.display = bool(self.meta_body)
        yield meta


class DiffBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("n", "next_hunk", "Next hunk", show=False),
        Binding("p", "previous_hunk", "Previous hunk", show=False),
        Binding("f", "toggle_hunk_fold", "Fold hunk", show=False),
    ]

    def __init__(self, diff: TuiDiffView, *, theme: str = "dark", width: int | None = None) -> None:
        self.display_model = transcript_display("diff")
        super().__init__(classes="transcript-block diff-block")
        self.diff = diff
        self.body = render_unified_diff_text(diff)
        self.renderable = render_unified_diff_rich(diff, theme=theme, width=width)
        self.current_hunk = 0
        self.folded = False

    def compose(self) -> ComposeResult:
        title = Label(self.display_model.label, classes="block-title")
        title.display = False
        yield title
        yield Static(self.renderable, classes="block-body")

    def action_next_hunk(self) -> None:
        if not self.diff.hunks:
            return
        self.current_hunk = min(len(self.diff.hunks) - 1, self.current_hunk + 1)
        self._update_hunk_status()

    def action_previous_hunk(self) -> None:
        if not self.diff.hunks:
            return
        self.current_hunk = max(0, self.current_hunk - 1)
        self._update_hunk_status()

    def action_toggle_hunk_fold(self) -> None:
        self.folded = not self.folded
        body = self.query_one(".block-body", Static)
        if self.folded:
            body.update(f"{self.diff.path or 'file'} (+{self.diff.added} -{self.diff.removed})\n... hunk folded ...")
        else:
            body.update(self.renderable)
        self._update_hunk_status()

    def _update_hunk_status(self) -> None:
        title = "Diff"
        if self.diff.hunks:
            title = f"Diff hunk {self.current_hunk + 1}/{len(self.diff.hunks)}"
            if self.folded:
                title += " folded"
        self.query_one(".block-title", Label).update(title)


class ErrorBlock(TranscriptBlock):
    def __init__(self, error: str) -> None:
        display = transcript_display("error")
        super().__init__(display.label, error, classes=display.css_class, kind="error")


class UsageLine(Static, can_focus=False):
    def __init__(self, text: str) -> None:
        self.display_model = transcript_display("usage")
        self.line = f"Usage  {text}"
        super().__init__(self.line, classes="usage-line")
        self.body = text


class QuestionBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("enter", "submit", "Submit"),
        Binding("space", "toggle_selected", "Toggle", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    selected_values = reactive(frozenset[str]())
    custom_mode = reactive(False)

    class Answered(Message):
        def __init__(self, question: str, answer: str) -> None:
            self.question = question
            self.answer = answer
            super().__init__()

    class Cancelled(Message):
        pass

    def __init__(self, question: AskUserQuestionItem) -> None:
        self.display_model = transcript_display("decision")
        super().__init__(classes="interaction-block question-block")
        self.question = question
        self.options = build_options(question)
        self.body = question.question
        self._refreshing_options = False
        self._option_list: QuestionOptionList | None = None
        self._custom_input: QuestionTextArea | None = None

    def compose(self) -> ComposeResult:
        yield Label(self.display_model.label, classes="block-title")
        yield Static(self.question.question, classes="block-body")
        self._option_list = QuestionOptionList(
            *[
                Option(
                    _question_option_label(option, selected=False),
                    id=option.value,
                )
                for option in self.options
            ],
            id="question-options",
        )
        self._custom_input = QuestionTextArea(id="question-custom")
        self._custom_input.display = False
        yield self._option_list
        yield self._custom_input

    def on_mount(self) -> None:
        self._question_options().focus()
        if not self.question.multi_select and self.options:
            self.selected_values = frozenset({self.options[0].value})
            self._refresh_options()

    @on(OptionList.OptionHighlighted, "#question-options")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self.sync_single_selection_to_highlight()

    def sync_single_selection_to_highlight(self) -> None:
        if self._refreshing_options or self.question.multi_select:
            return
        option = self._highlighted_option()
        if option is None:
            return
        self.selected_values = frozenset({option.value})
        self._refresh_options()

    @on(OptionList.OptionSelected, "#question-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        value = str(event.option_id or "")
        if self.question.multi_select:
            values = set(self.selected_values)
            if value in values:
                values.remove(value)
            else:
                values.add(value)
            self.selected_values = frozenset(values)
            self.custom_mode = OTHER_VALUE in values
            self._refresh_options()
            if self.custom_mode:
                self._focus_custom()
            return
        option = self._option_by_value(value)
        if option is None:
            return
        self.selected_values = frozenset({option.value})
        self.custom_mode = option.is_other
        self._refresh_options()
        if option.is_other:
            self._focus_custom()
            return
        answer = build_answer_for_question(self.question, option, [], "")
        if answer:
            self.post_message(self.Answered(self.question.question, answer))

    @on(QuestionTextArea.Submitted)
    def on_custom_submitted(self, event: QuestionTextArea.Submitted) -> None:
        event.stop()
        self.action_submit()

    def action_toggle_selected(self) -> None:
        if not self.question.multi_select:
            option = self._highlighted_option()
            if option is None:
                return
            self.selected_values = frozenset({option.value})
            self.custom_mode = option.is_other
            self._refresh_options()
            if option.is_other:
                self._focus_custom()
            return
        option = self._highlighted_option()
        if option is None:
            return
        values = set(self.selected_values)
        if option.value in values:
            values.remove(option.value)
        else:
            values.add(option.value)
        self.selected_values = frozenset(values)
        self.custom_mode = OTHER_VALUE in values
        self._refresh_options()
        if self.custom_mode:
            self._focus_custom()

    def action_submit(self) -> None:
        if self.question.multi_select:
            answer = build_answer_for_question(
                self.question,
                None,
                list(self.selected_values),
                self._custom_text(),
            )
        else:
            option = self._selected_single_option() or self._highlighted_option()
            answer = build_answer_for_question(
                self.question,
                option,
                [],
                self._custom_text() if option is not None and option.is_other else "",
            )
        if answer:
            self.post_message(self.Answered(self.question.question, answer))

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())

    def _option_by_value(self, value: str) -> AskUserQuestionOptionEntry | None:
        return next((option for option in self.options if option.value == value), None)

    def _highlighted_option(self) -> AskUserQuestionOptionEntry | None:
        option_list = self._question_options()
        highlighted = option_list.highlighted_option
        if highlighted is None or highlighted.id is None:
            return None
        return self._option_by_value(str(highlighted.id))

    def _selected_single_option(self) -> AskUserQuestionOptionEntry | None:
        if self.question.multi_select or not self.selected_values:
            return None
        return self._option_by_value(next(iter(self.selected_values)))

    def _custom_text(self) -> str:
        return self._question_custom().text.strip()

    def _focus_custom(self) -> None:
        custom = self._question_custom()
        custom.display = True
        self.call_after_refresh(custom.focus)

    def _refresh_options(self) -> None:
        option_list = self._question_options()
        highlighted_id = (
            str(option_list.highlighted_option.id)
            if option_list.highlighted_option is not None and option_list.highlighted_option.id is not None
            else None
        )
        self._refreshing_options = True
        try:
            option_list.clear_options()
            option_list.add_options(
                [
                    Option(
                        _question_option_label(option, selected=option.value in self.selected_values),
                        id=option.value,
                    )
                    for option in self.options
                ]
            )
            target_id = highlighted_id
            if not self.question.multi_select and self.selected_values:
                target_id = next(iter(self.selected_values))
            elif target_id is None and self.selected_values:
                target_id = next(iter(self.selected_values))
            if target_id is not None:
                for index, option in enumerate(self.options):
                    if option.value == target_id:
                        option_list.highlighted = index
                        break
            option_list.refresh(layout=True)
        finally:
            self._refreshing_options = False
        self._question_custom().display = self.custom_mode

    def _question_options(self) -> QuestionOptionList:
        if self._option_list is None:
            raise RuntimeError("Question option list is not mounted.")
        return self._option_list

    def _question_custom(self) -> QuestionTextArea:
        if self._custom_input is None:
            raise RuntimeError("Question custom input is not mounted.")
        return self._custom_input


class AuditDecisionBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("enter", "submit", "Submit"),
        Binding("escape", "reject", "Reject"),
        Binding("space", "toggle_preview", "Preview", show=False),
    ]

    class Decided(Message):
        def __init__(self, outcome: str) -> None:
            self.outcome = outcome
            super().__init__()

    def __init__(
        self,
        item: PendingApproval,
        *,
        project_root: str | Path | None = None,
        palette: UiPalette | None = None,
        width: int | None = None,
    ) -> None:
        self.display_model = transcript_display("decision")
        super().__init__(classes="interaction-block question-block audit-decision-block")
        self.item = item
        self.project_root = project_root
        self.palette = palette or DARK_PALETTE
        self.width = width
        self.expanded = False
        self.completed_outcome: str | None = None
        self._title = ""
        self._summary = ""
        self._preview_text = ""
        self._refresh_view_data()

    def compose(self) -> ComposeResult:
        yield Label(self.display_model.label, classes="block-title")
        yield Static(self._title, id="audit-decision-title", classes="block-body")
        yield Static(self._summary, id="audit-decision-summary", classes="tool-details")
        preview = Static(self._preview_text, id="audit-decision-preview", classes="tool-details")
        preview.display = False
        yield preview
        yield OptionList(
            Option("Approve", id="approve"),
            Option("Reject", id="reject"),
            id="audit-decision-options",
        )

    def on_mount(self) -> None:
        options = self.query_one("#audit-decision-options", OptionList)
        options.highlighted = 0
        options.focus()

    @on(OptionList.OptionSelected, "#audit-decision-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._complete(str(event.option_id or "reject"))

    def action_submit(self) -> None:
        options = self.query_one("#audit-decision-options", OptionList)
        index = options.highlighted if options.highlighted is not None else 0
        self._complete(str(options.get_option_at_index(index).id or "reject"))

    def action_reject(self) -> None:
        self._complete("reject")

    def action_toggle_preview(self) -> None:
        if not self._preview_text:
            return
        self.expanded = not self.expanded
        self.query_one("#audit-decision-preview", Static).display = self.expanded

    def _complete(self, outcome: str) -> None:
        if self.completed_outcome is not None:
            return
        self.completed_outcome = "approve" if outcome == "approve" else "reject"
        self.query_one("#audit-decision-options", OptionList).display = False
        self.post_message(self.Decided(self.completed_outcome))

    def _refresh_view_data(self) -> None:
        view = build_approval_view(
            self.item,
            palette=self.palette,
            project_root=self.project_root,
            expanded=True,
            width=self.width,
        )
        self._title = view.title
        self._summary = f"{view.target_label}: {view.target or '-'}"
        if view.metadata:
            self._summary += "\n" + "\n".join(f"{label}: {value}" for label, value in view.metadata)
        self._preview_text = view.preview or ""


@dataclass(frozen=True)
class InlineChoiceOption:
    label: str
    value: str
    description: str = ""


class InlineChoiceBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("enter", "submit", "Submit"),
        Binding("escape", "cancel", "Cancel"),
        Binding("up", "previous_choice", "Previous", show=False),
        Binding("down", "next_choice", "Next", show=False),
    ]

    class Chosen(Message):
        def __init__(self, value: str | None) -> None:
            self.value = value
            super().__init__()

    def __init__(self, title: str, options: list[InlineChoiceOption]) -> None:
        self.display_model = transcript_display("decision")
        super().__init__(classes="interaction-block question-block inline-choice-block")
        self.title_text = title
        self.options = list(options)
        self.completed_value: str | None = None

    def compose(self) -> ComposeResult:
        yield Label(self.title_text, classes="block-title")
        yield OptionList(
            *[
                Option(
                    _inline_choice_prompt(option),
                    id=option.value,
                )
                for option in self.options
            ],
            id="inline-choice-options",
            classes="inline-choice-options",
        )
        yield Static("Enter select · ↑/↓ move · Esc cancel", classes="screen-help")

    def on_mount(self) -> None:
        options = self.query_one("#inline-choice-options", OptionList)
        options.highlighted = 0 if self.options else None
        options.focus()

    @on(OptionList.OptionSelected, "#inline-choice-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._complete(str(event.option_id) if event.option_id is not None else None)

    def action_submit(self) -> None:
        options = self.query_one("#inline-choice-options", OptionList)
        if options.option_count == 0:
            self._complete(None)
            return
        index = options.highlighted if options.highlighted is not None else 0
        self._complete(str(options.get_option_at_index(index).id or ""))

    def action_cancel(self) -> None:
        self._complete(None)

    def action_previous_choice(self) -> None:
        self._move_choice(-1)

    def action_next_choice(self) -> None:
        self._move_choice(1)

    def _move_choice(self, delta: int) -> None:
        options = self.query_one("#inline-choice-options", OptionList)
        if options.option_count == 0:
            return
        current = options.highlighted if options.highlighted is not None else 0
        options.highlighted = (current + delta) % options.option_count
        options.scroll_to_highlight()

    def _complete(self, value: str | None) -> None:
        if self.completed_value is not None:
            return
        self.completed_value = value
        self.query_one("#inline-choice-options", OptionList).display = False
        self.post_message(self.Chosen(value))


def _inline_choice_prompt(option: InlineChoiceOption) -> Text:
    prompt = Text()
    prompt.append(option.label, style="bold #e5e7eb")
    if option.description:
        prompt.append(f"  {option.description}", style="#aab3d0")
    return prompt


def _tool_output_title(view: ToolOutputView, *, project_root: Path | None = None) -> str:
    detail = view.path or ""
    if view.name == "load_skill" and view.metadata:
        detail = str(view.metadata.get("name") or detail)
    if detail and project_root is not None:
        detail = _relative_tool_path(detail, project_root=project_root)
    status = view.status
    name = _tool_title_name(view.name)
    return f"{name} {status}" + (f" - {detail}" if detail else "")


def _relative_tool_path(path: str, *, project_root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve()))
    except (OSError, ValueError):
        return path


def _tool_title_name(name: str) -> str:
    if name.startswith("subagent_"):
        subagent_name = name.removeprefix("subagent_").replace("_", "-")
        return f"Subagent {subagent_name}"
    return format_tool_display_name(name)


def _tool_arguments_body(name: str, arguments: str) -> str:
    if name == "AskUserQuestion":
        return ""
    if not arguments.strip():
        return ""
    return build_tool_params_snippet({"name": name, "arguments": arguments})


def _tool_output_body(view: ToolOutputView) -> str:
    if view.name == "AskUserQuestion":
        return "Waiting for user input." if view.await_user_response else _compact_text(view.output or view.summary)
    if view.name == "load_skill" and view.ok is True:
        metadata = view.metadata or {}
        name = str(metadata.get("name") or "skill")
        root = str(metadata.get("root") or metadata.get("path") or "")
        description = str(metadata.get("description") or "").strip()
        lines = [f"Loaded skill: {name}"]
        if description:
            lines.append(f"Description: {description}")
        if root:
            lines.append(f"Root: {root}")
        return "\n".join(lines)
    if view.name == "shell":
        return _shell_body(view)
    if view.name == "read":
        return _read_body(view)
    if view.name == "todo_write":
        return _todo_body(view)
    if view.name in {"WebSearch", "WebFetch"}:
        return _web_body(view)
    if _is_mcp_view(view):
        return _mcp_body(view)
    if view.ok is False and view.metadata:
        detail = format_tool_failure_detail(view.metadata)
        if detail:
            return detail
    return _compact_text(view.error or view.output or view.summary)


def _tool_output_details(view: ToolOutputView) -> str:
    if view.name == "AskUserQuestion":
        return ""
    if view.status == "retryable" and view.metadata:
        recovery = str(view.metadata.get("recovery") or "").strip()
        parse_error = str(view.metadata.get("parse_error") or view.error or "").strip()
        details = "\n".join(line for line in [recovery, parse_error] if line)
        return _compact_text(details, max_lines=8) if details else ""
    text = view.error or view.output or ""
    if not text:
        return ""
    compact = _compact_text(text)
    return "" if compact == text.strip() else text.strip()


def _shell_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    lines = [
        f"Status: {view.status}",
        f"Exit code: {metadata.get('exit_code', metadata.get('exitCode', 'unknown'))}",
    ]
    duration = metadata.get("duration_ms", metadata.get("durationMs"))
    if duration is not None:
        lines.append(f"Duration: {duration} ms")
    cwd = metadata.get("cwd")
    if cwd:
        lines.append(f"Cwd: {cwd}")
    shell_path = metadata.get("shellPath") or metadata.get("shell_path")
    if shell_path:
        lines.append(f"Shell: {shell_path}")
    dialect = metadata.get("commandDialect") or metadata.get("command_dialect")
    if dialect:
        lines.append(f"Dialect: {dialect}")
    command = metadata.get("command")
    if command:
        lines.append(f"Command: {command}")
    if metadata.get("outputTruncated") or metadata.get("captureTruncated"):
        lines.append("Truncated: true")
    output = _compact_text(view.error or view.output)
    if output:
        lines.extend(["", output])
    return "\n".join(str(line) for line in lines)


def _local_command_title(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    command = str(metadata.get("command") or "").strip()
    status = view.status
    title = f"Shell {status}"
    return f"{title} - {command}" if command else title


def _local_command_output_body(view: ToolOutputView) -> str:
    text = (view.output or "").strip()
    if not text and view.error:
        text = str(view.error).strip()
    if not text:
        return "(no output)"
    return _compact_text(text, max_lines=80)


def _local_command_meta_body(view: ToolOutputView) -> str:
    if view.ok is True:
        return ""
    metadata = view.metadata or {}
    parts: list[str] = []
    exit_code = metadata.get("exit_code", metadata.get("exitCode"))
    if exit_code not in {None, 0}:
        parts.append(f"exit {exit_code}")
    duration = metadata.get("duration_ms", metadata.get("durationMs"))
    if duration is not None:
        parts.append(f"{duration} ms")
    cwd = metadata.get("cwd")
    if cwd:
        parts.append(str(cwd))
    shell_kind = metadata.get("shellKind") or metadata.get("shell_kind")
    if shell_kind:
        parts.append(str(shell_kind))
    if metadata.get("displayOutputTruncated") or metadata.get("captureTruncated"):
        parts.append("truncated")
    return " · ".join(parts)


def _read_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    lines = []
    if view.path:
        lines.append(f"Path: {view.path}")
    if metadata.get("pages"):
        lines.append(f"Pages: {metadata['pages']}")
    if metadata.get("start_line") or metadata.get("startLine"):
        lines.append(f"Start: {metadata.get('start_line', metadata.get('startLine'))}")
    preview = _compact_text(view.error or view.output, max_lines=12, max_chars=1200)
    if preview:
        lines.extend(["", preview] if lines else [preview])
    return "\n".join(lines)


def _todo_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    todos = metadata.get("todos")
    items, error = normalize_todo_items(todos)
    if error is None and items:
        counts = todo_counts(items)
        total = counts["total"]
        completed = counts["completed"]
        percent = round((completed / total) * 100) if total else 0
        current = next((item for item in items if item.status == "in_progress"), None)
        if current is None:
            current = next((item for item in items if item.status == "pending"), None)
        lines = [
            f"Progress  {_progress_bar(completed, total)}  {completed}/{total} completed ({percent}%)",
            (
                "Status    "
                f"{counts['completed']} done | "
                f"{counts['in_progress']} active | "
                f"{counts['pending']} pending"
            ),
        ]
        if current is not None:
            lines.append(f"Current   {current.id}: {current.content}")
        lines.append("")
        lines.append("Tasks")
        for item in items[:12]:
            marker = _todo_marker(item.status)
            lines.append(f"  {marker} {item.id}: {item.content}")
        if len(items) > 12:
            lines.append("  ... todos truncated ...")
        return "\n".join(lines)
    return _compact_text(view.error or view.output or view.summary)


def _web_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    lines = []
    preview = _compact_text(view.error or view.output)
    if preview:
        lines.append(preview)
    url = metadata.get("url") or metadata.get("final_url") or metadata.get("finalUrl")
    provider = metadata.get("provider")
    metadata_lines = []
    if provider:
        metadata_lines.append(f"Provider: {provider}")
    if url:
        metadata_lines.append(f"URL: {url}")
    if metadata_lines:
        lines.extend(["", *metadata_lines] if lines else metadata_lines)
    return "\n".join(str(line) for line in lines)


def _is_mcp_view(view: ToolOutputView) -> bool:
    metadata = view.metadata or {}
    return bool(
        metadata.get("mcp_server")
        or metadata.get("server")
        or metadata.get("serverName")
        or metadata.get("mcp_tool")
        or metadata.get("tool")
        or str(metadata.get("kind") or "").startswith("mcp")
    )


def _mcp_body(view: ToolOutputView) -> str:
    metadata = view.metadata or {}
    lines = [f"Status: {view.status}"]
    server = metadata.get("mcp_server") or metadata.get("server") or metadata.get("serverName")
    tool = metadata.get("mcp_tool") or metadata.get("tool")
    state = metadata.get("state") or metadata.get("cleanup") or metadata.get("availability")
    if server:
        lines.append(f"Server: {server}")
    if tool:
        lines.append(f"Tool: {tool}")
    if state:
        lines.append(f"State: {state}")
    preview = _compact_text(view.error or view.output)
    if preview:
        lines.extend(["", preview])
    return "\n".join(str(line) for line in lines)


def _indent_block(text: str) -> str:
    if not text:
        return ""
    return "\n".join(f"  {line}" if line else "" for line in text.splitlines())


def _compact_text(text: str, *, max_lines: int = 8, max_chars: int = 900) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    compact = "\n".join(lines[:max_lines])
    truncated = len(lines) > max_lines
    if len(compact) > max_chars:
        compact = compact[: max_chars - 3].rstrip() + "..."
        truncated = True
    if truncated:
        compact += "\n... output truncated ..."
    return compact


def _progress_bar(completed: int, total: int, *, width: int = 18) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    filled = round((completed / total) * width)
    filled = max(0, min(width, filled))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _todo_marker(status: str) -> str:
    if status == "completed":
        return "[x]"
    if status == "in_progress":
        return "[>]"
    return "[ ]"


def _question_option_label(option: AskUserQuestionOptionEntry, *, selected: bool) -> str:
    marker = "[x]" if selected else "[ ]"
    detail = f" - {option.description}" if option.description else ""
    return f"{marker} {option.label}{detail}"
