from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Markdown, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from deepy.tui.diff import TuiDiffView, render_unified_diff_rich, render_unified_diff_text
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


class PromptTextArea(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Send", priority=True),
        Binding("shift+enter", "newline", "Newline", priority=True),
        Binding("tab", "accept_suggestion", "Accept suggestion", priority=True, show=False),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    class SuggestionAccepted(Message):
        pass

    def action_submit(self) -> None:
        text = self.text.strip()
        if not text:
            return
        self.post_message(self.Submitted(text))
        self.clear()

    def action_newline(self) -> None:
        self.insert("\n")

    def action_accept_suggestion(self) -> None:
        self.post_message(self.SuggestionAccepted())


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

    def compose(self) -> ComposeResult:
        yield Label("Prompt", id="prompt-title")
        yield PromptTextArea(id="prompt-input")
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
            return
        option_list.display = True
        option_list.add_options([Option(suggestion, id=suggestion) for suggestion in suggestions[:8]])

    def accept_first_suggestion(self) -> bool:
        if not self.suggestions:
            return False
        prompt = self.query_one("#prompt-input", PromptTextArea)
        prompt.text = self._apply_suggestion(prompt.text, self.suggestions[0])
        prompt.move_cursor((0, len(prompt.text)))
        self.refresh_suggestions(prompt.text)
        return True

    def _suggestions_for_text(self, text: str) -> list[str]:
        token = text.strip()
        if token.startswith("/") and "\n" not in token:
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
        return text[: mention.start - 1] + value + " "


class StatusBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("Deepy TUI experimental", id="status-left")
        yield Label("Idle", id="status-right")

    def update_status(self, status: str) -> None:
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
    ) -> None:
        super().__init__(label, body, classes="tool-block")
        self.call_id = call_id
        self.arguments = arguments.strip()

    @classmethod
    def from_call(cls, name: str, arguments: str, *, call_id: str) -> ToolBlock:
        display_name = format_tool_display_name(name or "tool")
        params = _tool_arguments_body(name or "tool", arguments)
        return cls(
            f"{display_name} running",
            f"Parameters\n  {params}" if params else "Running",
            call_id=call_id,
            arguments=params,
        )

    @classmethod
    def from_output(cls, view: ToolOutputView, *, call_id: str = "") -> ToolBlock:
        body = _tool_output_body(view)
        return cls(_tool_output_title(view), body, call_id=call_id)

    def update_from_output(self, view: ToolOutputView) -> None:
        self.title = _tool_output_title(view)
        output_body = _tool_output_body(view)
        self.body = (
            f"Parameters\n  {self.arguments}\n\nOutput\n{_indent_block(output_body)}"
            if self.arguments and output_body
            else output_body
        )
        self.query_one(".block-title", Label).update(self.title)
        self.query_one(".block-body", Static).update(self.body)


class DiffBlock(Vertical, can_focus=True):
    def __init__(self, diff: TuiDiffView, *, theme: str = "dark", width: int | None = None) -> None:
        super().__init__(classes="transcript-block diff-block")
        self.diff = diff
        self.body = render_unified_diff_text(diff)
        self.renderable = render_unified_diff_rich(diff, theme=theme, width=width)

    def compose(self) -> ComposeResult:
        yield Label("Diff", classes="block-title")
        yield Static(self.renderable, classes="block-body")


class ErrorBlock(TranscriptBlock):
    def __init__(self, error: str) -> None:
        super().__init__("Error", error, classes="error-block")


class UsageLine(Static, can_focus=False):
    def __init__(self, text: str) -> None:
        self.line = f"Usage  {text}"
        super().__init__(self.line, classes="usage-line")
        self.body = text


def _tool_output_title(view: ToolOutputView) -> str:
    detail = view.path or ""
    if view.name == "load_skill" and view.metadata:
        detail = str(view.metadata.get("name") or detail)
    status = view.status
    name = format_tool_display_name(view.name)
    return f"{name} {status}" + (f" - {detail}" if detail else "")


def _tool_arguments_body(name: str, arguments: str) -> str:
    if not arguments.strip():
        return ""
    return build_tool_params_snippet({"name": name, "arguments": arguments})


def _tool_output_body(view: ToolOutputView) -> str:
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
    return _compact_text(view.error or view.output or view.summary)


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
