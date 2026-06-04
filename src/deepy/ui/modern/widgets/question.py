"""Ask-user-question interaction block for the Modern UI."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from deepy.ui.modern.render.tool_format import _question_option_label
from deepy.ui.modern.render.transcript import transcript_display
from deepy.ui.shared.input.ask_user_question import (
    AskUserQuestionItem,
    AskUserQuestionOptionEntry,
    OTHER_VALUE,
    build_answer_for_question,
    build_options,
)


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
        self._suppress_next_highlight_sync = False
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
        if self._refreshing_options or self.question.multi_select or self.custom_mode:
            return
        if self._suppress_next_highlight_sync:
            self._suppress_next_highlight_sync = False
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
        highlighted_index = option_list.highlighted
        if highlighted_index is not None and 0 <= highlighted_index < len(self.options):
            return self.options[highlighted_index]
        highlighted = option_list.highlighted_option
        if highlighted is not None and highlighted.id is not None:
            return self._option_by_value(str(highlighted.id))
        return None

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
                        self._suppress_next_highlight_sync = True
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
