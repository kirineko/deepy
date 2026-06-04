"""Audit-approval and inline-choice interaction blocks for the Modern UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from deepy.audit import PendingApproval
from deepy.ui.modern.render.transcript import transcript_display
from deepy.ui.shared.render.audit_approval_panel import build_approval_view
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette


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
        yield Static(self._summary, id="audit-decision-summary", classes="block-body audit-decision-summary")
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
        metadata = _tui_approval_metadata(self.item, view.metadata)
        if metadata:
            self._summary += "\n" + "\n".join(f"{label}: {value}" for label, value in metadata)
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
    prompt.append(option.label, style="bold")
    if option.description:
        prompt.append(f"  {option.description}", style="dim")
    return prompt


def _tui_approval_metadata(
    item: PendingApproval,
    metadata: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    tool_name = item.tool_name or item.name or ""
    if tool_name == "shell" or item.action_kind == "command":
        return tuple((label, value) for label, value in metadata if label != "description")
    return metadata
