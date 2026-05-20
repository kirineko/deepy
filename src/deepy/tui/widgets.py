from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Markdown, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from deepy.tui.diff import TuiDiffView, render_unified_diff_rich, render_unified_diff_text
from deepy.todos import normalize_todo_items, todo_counts
from deepy.ui.ask_user_question import (
    AskUserQuestionItem,
    AskUserQuestionOptionEntry,
    OTHER_VALUE,
    build_answer_for_question,
    build_options,
)
from deepy.ui.file_mentions import (
    FileMentionDiscovery,
    extract_file_mention_fragment,
    rank_file_mention_candidates,
)
from deepy.ui.message_view import (
    ToolOutputView,
    build_tool_params_snippet,
    format_tool_display_name,
)
from deepy.ui.slash_commands import (
    SlashCommandItem,
    filter_slash_commands,
    format_slash_command_label,
)


_KITTY_TEXT_SEQUENCE_RE = re.compile(r"(?:\x1b)?\[([0-9:;]+)u")


def decode_kitty_text_sequences(text: str) -> str:
    """Decode Kitty keyboard-protocol text sequences leaked as plain input."""

    def replace(match: re.Match[str]) -> str:
        payload = match.group(1)
        fields = payload.split(";")
        if len(fields) < 3:
            return match.group(0)
        encoded_text = ";".join(fields[2:])
        if not encoded_text:
            return match.group(0)
        values: list[int] = []
        for item in re.split(r"[:;]", encoded_text):
            if not item.isdecimal():
                return match.group(0)
            value = int(item)
            if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                return match.group(0)
            if value < 0x20 or 0x7F <= value <= 0x9F:
                return match.group(0)
            values.append(value)
        return "".join(chr(value) for value in values)

    return _KITTY_TEXT_SEQUENCE_RE.sub(replace, text)


def _end_cursor_location(text: str) -> tuple[int, int]:
    lines = text.splitlines() or [""]
    if text.endswith("\n"):
        return (len(lines), 0)
    return (len(lines) - 1, len(lines[-1]))


class _KeyboardProtocolTextMixin:
    _normalizing_keyboard_protocol_text = False

    def _normalize_keyboard_protocol_text(self) -> bool:
        if self._normalizing_keyboard_protocol_text:
            return False
        normalized = decode_kitty_text_sequences(self.text)
        if normalized == self.text:
            return False
        self._normalizing_keyboard_protocol_text = True
        try:
            self.text = normalized
            cast(TextArea, self).move_cursor(_end_cursor_location(normalized))
        finally:
            self._normalizing_keyboard_protocol_text = False
        return True


class PromptTextArea(_KeyboardProtocolTextMixin, TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Send", priority=True),
        Binding("ctrl+j", "newline", "Newline", priority=True),
        Binding("tab", "accept_suggestion", "Accept suggestion", priority=True, show=False),
        Binding("ctrl+up", "history_previous", "History previous", priority=True, show=False),
        Binding("ctrl+down", "history_next", "History next", priority=True, show=False),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    class SuggestionAccepted(Message):
        pass

    class HistoryPrevious(Message):
        pass

    class HistoryNext(Message):
        pass

    @on(TextArea.Changed)
    def on_keyboard_protocol_text_changed(self, event: TextArea.Changed) -> None:
        if self._normalize_keyboard_protocol_text():
            event.stop()

    def action_submit(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel) and panel.accept_selected_suggestion():
            return
        text = self.text.strip()
        if not text:
            return
        self.post_message(self.Submitted(text))
        self.clear()

    def action_newline(self) -> None:
        self.insert("\n")

    def action_accept_suggestion(self) -> None:
        panel = self.parent
        if isinstance(panel, PromptPanel) and panel.accept_selected_suggestion():
            return
        if isinstance(panel, PromptPanel) and panel.accept_input_suggestion():
            return
        self.post_message(self.SuggestionAccepted())

    def action_cursor_right(self, select: bool = False) -> None:
        panel = self.parent
        if not select and isinstance(panel, PromptPanel) and panel.accept_input_suggestion():
            return
        super().action_cursor_right(select)

    def action_history_previous(self) -> None:
        self.post_message(self.HistoryPrevious())

    def action_history_next(self) -> None:
        self.post_message(self.HistoryNext())

    def action_cursor_up(self, select: bool = False) -> None:
        panel = self.parent
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
        if not select and self.cursor_at_last_line:
            self.action_history_next()
            return
        super().action_cursor_down(select)


class QuestionTextArea(_KeyboardProtocolTextMixin, TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("ctrl+j", "newline", "Newline", priority=True),
    ]

    class Submitted(Message):
        pass

    @on(TextArea.Changed)
    def on_keyboard_protocol_text_changed(self, event: TextArea.Changed) -> None:
        if self._normalize_keyboard_protocol_text():
            event.stop()

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


class PromptPanel(Vertical):
    def __init__(
        self,
        slash_commands: list[SlashCommandItem],
        project_root: Path,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.slash_commands = slash_commands
        self.discovery = FileMentionDiscovery(project_root)
        self.suggestions: list[str] = []
        self.input_suggestion: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("Prompt", id="prompt-title")
        yield PromptTextArea(id="prompt-input")
        yield Label("", id="prompt-ghost")
        yield OptionList(id="prompt-suggestions")

    @on(TextArea.Changed, "#prompt-input")
    def on_prompt_changed(self, event: TextArea.Changed) -> None:
        self.refresh_suggestions(event.text_area.text)

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
        option_list.add_options([Option(suggestion, id=suggestion) for suggestion in suggestions[:8]])
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
            if any(item.label == token for item in self.slash_commands):
                return []
            return [
                f"{format_slash_command_label(item)}  {item.description}"
                for item in filter_slash_commands(self.slash_commands, token)
            ]
        mention = extract_file_mention_fragment(text)
        if mention is None:
            return []
        paths = (
            self.discovery.top_level_paths()
            if "/" not in mention.fragment
            else self.discovery.deep_paths(mention.fragment.rsplit("/", 1)[0])
        )
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
        ghost = self.query_one("#prompt-ghost", Label)
        prompt = self.query_one("#prompt-input", PromptTextArea)
        option_list = self.query_one("#prompt-suggestions", OptionList)
        visible = bool(
            self.input_suggestion
            and not prompt.text
            and not (option_list.display and option_list.option_count > 0)
        )
        ghost.display = visible
        ghost.update(self.input_suggestion or "")


class StatusBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("Deepy TUI experimental", id="status-left")
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

    def __init__(self, title: str, body: str = "", *, classes: str | None = None) -> None:
        super().__init__(classes=f"transcript-block {classes or ''}".strip())
        self.title = title
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
        super().__init__(classes="transcript-block info-block")
        self.body = text

    def compose(self) -> ComposeResult:
        yield Static(self.body, classes="block-body")


class UserBlock(TranscriptBlock):
    def __init__(self, text: str) -> None:
        super().__init__("You", text, classes="user-block")


class ThinkingBlock(TranscriptBlock):
    def __init__(self, text: str = "") -> None:
        super().__init__("Thinking", text, classes="thinking-block")

    def update_text(self, text: str) -> None:
        self.body = text
        self.query_one(".block-body", Static).update(text)


class AssistantBlock(Vertical, can_focus=True):
    def __init__(self, markdown: str = "") -> None:
        super().__init__(classes="transcript-block assistant-block")
        self.markdown = markdown

    def compose(self) -> ComposeResult:
        yield Label("Deepy", classes="block-title")
        yield Markdown(self.markdown, classes="block-markdown")

    def update_markdown(self, markdown: str) -> None:
        self.markdown = markdown
        self.query_one(Markdown).update(markdown)


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
    ) -> None:
        classes = "tool-block todo-block" if tool_name == "todo_write" else "tool-block"
        super().__init__(label, body, classes=classes)
        self.call_id = call_id
        self.arguments = arguments.strip()
        self.details = details.strip()
        self.waiting_for_user = waiting_for_user
        self.tool_name = tool_name

    @classmethod
    def from_call(cls, name: str, arguments: str, *, call_id: str) -> ToolBlock:
        display_name = format_tool_display_name(name or "tool")
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
    def from_output(cls, view: ToolOutputView, *, call_id: str = "") -> ToolBlock:
        body = _tool_output_body(view)
        return cls(
            _tool_output_title(view),
            body,
            call_id=call_id,
            details=_tool_output_details(view),
            waiting_for_user=view.await_user_response,
            tool_name=view.name,
        )

    def update_from_output(self, view: ToolOutputView) -> None:
        self.tool_name = view.name
        self.title = _tool_output_title(view)
        output_body = _tool_output_body(view)
        self.details = _tool_output_details(view)
        self.waiting_for_user = view.await_user_response
        self.body = (
            f"Parameters\n  {self.arguments}\n\nOutput\n{_indent_block(output_body)}"
            if self.arguments and output_body and view.name != "todo_write"
            else output_body
        )
        self.query_one(".block-title", Label).update(self.title)
        self.query_one(".block-body", Static).update(self.body)
        details = self.query_one(".tool-details", Static)
        details.update(self.details)
        details.display = bool(self.details and self.expanded)
        self.set_class(self.waiting_for_user, "-waiting")
        self.set_class(view.name == "todo_write", "todo-block")

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="block-title")
        yield Static(self.body, classes="block-body")
        detail = Static(self.details, classes="tool-details")
        detail.display = False
        yield detail

    def action_toggle_expand(self) -> None:
        super().action_toggle_expand()
        self.query_one(".tool-details", Static).display = bool(self.expanded and self.details)


class DiffBlock(Vertical, can_focus=True):
    BINDINGS = [
        Binding("n", "next_hunk", "Next hunk", show=False),
        Binding("p", "previous_hunk", "Previous hunk", show=False),
        Binding("f", "toggle_hunk_fold", "Fold hunk", show=False),
    ]

    def __init__(self, diff: TuiDiffView, *, theme: str = "dark", width: int | None = None) -> None:
        super().__init__(classes="transcript-block diff-block")
        self.diff = diff
        self.body = render_unified_diff_text(diff)
        self.renderable = render_unified_diff_rich(diff, theme=theme, width=width)
        self.current_hunk = 0
        self.folded = False

    def compose(self) -> ComposeResult:
        yield Label("Diff", classes="block-title")
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
        super().__init__("Error", error, classes="error-block")


class UsageLine(Static, can_focus=False):
    def __init__(self, text: str) -> None:
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
        super().__init__(classes="transcript-block question-block")
        self.question = question
        self.options = build_options(question)
        self.body = question.question
        self._refreshing_options = False

    def compose(self) -> ComposeResult:
        yield Label("Question", classes="block-title")
        yield Static(self.question.question, classes="block-body")
        yield QuestionOptionList(
            *[
                Option(
                    _question_option_label(option, selected=False),
                    id=option.value,
                )
                for option in self.options
            ],
            id="question-options",
        )
        custom = QuestionTextArea(id="question-custom")
        custom.display = False
        yield custom

    def on_mount(self) -> None:
        self.query_one("#question-options", OptionList).focus()
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
        option_list = self.query_one("#question-options", OptionList)
        highlighted = option_list.highlighted_option
        if highlighted is None or highlighted.id is None:
            return None
        return self._option_by_value(str(highlighted.id))

    def _selected_single_option(self) -> AskUserQuestionOptionEntry | None:
        if self.question.multi_select or not self.selected_values:
            return None
        return self._option_by_value(next(iter(self.selected_values)))

    def _custom_text(self) -> str:
        return self.query_one("#question-custom", TextArea).text.strip()

    def _focus_custom(self) -> None:
        custom = self.query_one("#question-custom", TextArea)
        custom.display = True
        custom.focus()

    def _refresh_options(self) -> None:
        option_list = self.query_one("#question-options", OptionList)
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
        finally:
            self._refreshing_options = False
        self.query_one("#question-custom", TextArea).display = self.custom_mode


def _tool_output_title(view: ToolOutputView) -> str:
    detail = view.path or ""
    if view.name == "load_skill" and view.metadata:
        detail = str(view.metadata.get("name") or detail)
    status = view.status
    name = format_tool_display_name(view.name)
    return f"{name} {status}" + (f" - {detail}" if detail else "")


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
    return _compact_text(view.error or view.output or view.summary)


def _tool_output_details(view: ToolOutputView) -> str:
    if view.name == "AskUserQuestion":
        return ""
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
