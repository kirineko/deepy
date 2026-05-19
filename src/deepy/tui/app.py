from __future__ import annotations

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import var
from textual.widgets import Footer, Header, Label, Static

from deepy.config import Settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.skills import discover_skills, find_skill, format_skills_for_terminal
from deepy.tui.diff import diff_view_from_tool_output
from deepy.tui.state import (
    TuiState,
    add_assistant_delta,
    add_reasoning_delta,
    request_interrupt,
    reset_turn_buffers,
    set_busy,
    set_quit_confirm,
    set_pending_questions,
    set_session_id,
    set_status,
    set_usage,
)
from deepy.tui.widgets import (
    AssistantBlock,
    DiffBlock,
    ErrorBlock,
    InfoBlock,
    PromptPanel,
    PromptTextArea,
    StatusBar,
    ThinkingBlock,
    ToolBlock,
    UsageLine,
    UserBlock,
)
from deepy.ui import parse_slash_command
from deepy.ui.message_view import parse_tool_output
from deepy.ui.slash_commands import build_slash_commands
from deepy.usage import format_usage_line


RunOnce = Callable[..., Coroutine[Any, Any, RunSummary]]


class StreamEventMessage(Message):
    def __init__(self, event: DeepyStreamEvent) -> None:
        self.event = event
        super().__init__()


class TurnCompleteMessage(Message):
    def __init__(self, summary: RunSummary) -> None:
        self.summary = summary
        super().__init__()


class TurnFailedMessage(Message):
    def __init__(self, error: Exception) -> None:
        self.error = error
        super().__init__()


class DeepyTuiApp(App[None]):
    """Experimental Textual UI for Deepy."""

    TITLE = "Deepy TUI"
    SUB_TITLE = "experimental"
    BINDINGS = [
        Binding("ctrl+d", "confirm_quit", "Quit", priority=True),
        Binding("escape", "interrupt_or_focus_prompt", "Interrupt", priority=True),
        Binding("ctrl+o", "toggle_help_panel", "Panel"),
        Binding("alt+up", "focus_previous_block", "Previous block"),
        Binding("alt+down", "focus_next_block", "Next block"),
    ]
    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #main-layout {
        height: 1fr;
        layout: horizontal;
    }

    #transcript {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        scrollbar-size-vertical: 1;
    }

    #side-panel {
        width: 30;
        display: none;
        border-left: solid $primary;
        padding: 1;
    }

    #side-panel.-visible {
        display: block;
    }

    PromptPanel {
        dock: bottom;
        height: auto;
        padding: 0 1 1 1;
        border-top: solid $primary;
        background: $panel;
    }

    #prompt-title {
        color: $text-muted;
        height: 1;
    }

    #prompt-input {
        height: auto;
        max-height: 8;
        border: tall transparent;
        background: transparent;
    }

    #prompt-input:focus {
        border: tall $accent;
    }

    #prompt-suggestions {
        height: auto;
        max-height: 8;
        display: none;
        border: round $accent;
    }

    StatusBar {
        height: 1;
        padding: 0 1;
        background: $boost;
    }

    #status-left {
        width: 1fr;
        color: $accent;
    }

    #status-right {
        width: auto;
        color: $text-muted;
    }

    .transcript-block {
        height: auto;
        margin: 1 0;
        padding: 0 1;
        border-left: solid $primary;
    }

    .transcript-block:focus {
        background: $boost;
        border-left: solid $accent;
    }

    .block-title {
        color: $accent;
        text-style: bold;
        height: 1;
    }

    .user-block {
        border-left: solid #38bdf8;
    }

    .user-block .block-title {
        color: #7dd3fc;
    }

    .info-block {
        color: $text-muted;
        border-left: solid #64748b;
        margin: 0 0 1 0;
    }

    .assistant-block {
        border-left: solid $success;
    }

    .assistant-block .block-title {
        color: $success;
    }

    .thinking-block {
        border-left: solid $warning;
        color: $text-muted;
    }

    .thinking-block .block-title {
        color: $warning;
    }

    .tool-block {
        border-left: solid $accent;
        background: $boost;
    }

    .tool-block .block-title {
        color: $accent;
    }

    .diff-block {
        border-left: solid $success;
    }

    .error-block {
        border-left: solid $error;
    }

    .usage-line {
        height: 1;
        margin: 0 0 1 1;
        padding: 0;
        color: $text-muted;
    }
    """

    state: var[TuiState] = var(TuiState())

    def __init__(
        self,
        *,
        settings: Settings,
        project_root: Path,
        run_once: RunOnce,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.project_root = project_root
        self.run_once = run_once
        self._assistant_block: AssistantBlock | None = None
        self._thinking_block: ThinkingBlock | None = None
        self._tool_blocks: dict[str, ToolBlock] = {}
        self._loaded_skill_names: list[str] = []
        self._focused_block_index = -1

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            yield VerticalScroll(id="transcript")
            with Vertical(id="side-panel"):
                yield Label("Status", classes="block-title")
                yield Static("", id="side-status")
        yield StatusBar(id="status-bar")
        yield PromptPanel(
            build_slash_commands(discover_skills(self.project_root)),
            self.project_root,
            id="prompt-panel",
        )
        yield Footer()

    async def on_mount(self) -> None:
        self._apply_theme()
        await self.query_one("#transcript", VerticalScroll).mount(
            InfoBlock(
                "Experimental Textual TUI. Press Ctrl+O for status, Enter to send, "
                "Shift+Enter for newline, Ctrl+D twice to exit."
            )
        )
        self._scroll_transcript_to_end()
        self.query_one("#prompt-input", PromptTextArea).focus()
        self._update_status("Idle")

    def _apply_theme(self) -> None:
        self.theme = "textual-light" if self.settings.ui.theme == "light" else "textual-dark"

    @on(PromptTextArea.Submitted)
    async def on_prompt_submitted(self, event: PromptTextArea.Submitted) -> None:
        event.stop()
        if self.state.busy:
            self.notify("Deepy is still working.", severity="warning")
            return
        if await self._handle_prompt_command(event.text):
            return
        await self._append_block(UserBlock(event.text))
        self.state = set_busy(reset_turn_buffers(self.state), True, "Running")
        self._assistant_block = None
        self._thinking_block = None
        self._tool_blocks.clear()
        self._update_status("Running")
        self.run_model_turn(event.text, list(self._loaded_skill_names))

    async def _handle_prompt_command(self, text: str) -> bool:
        slash = parse_slash_command(text)
        if slash is None:
            return False
        if slash.name in {"exit", "quit"}:
            self.exit()
            return True
        if slash.name == "skills":
            return await self._handle_skills_command(slash.argument)
        if slash.name.startswith("skill:"):
            skill_name = slash.name.removeprefix("skill:")
            skill = find_skill(self.project_root, skill_name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {skill_name}"))
                return True
            request = slash.argument or f"Use the {skill.name} skill."
            await self._append_block(UserBlock(text))
            self.state = set_busy(reset_turn_buffers(self.state), True, "Running")
            self._assistant_block = None
            self._thinking_block = None
            self._tool_blocks.clear()
            self._update_status(f"Using skill {skill.name}")
            self.run_model_turn(request, [skill.name])
            return True
        return False

    async def _handle_skills_command(self, argument: str) -> bool:
        action, _, rest = argument.partition(" ")
        action = action.strip().lower()
        name = rest.strip()
        if action in {"", "list"}:
            await self._append_block(UserBlock(format_skills_for_terminal(discover_skills(self.project_root))))
            return True
        if action == "use":
            if not name:
                await self._append_block(ErrorBlock("Usage: /skills use NAME"))
                return True
            skill = find_skill(self.project_root, name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {name}"))
                return True
            if skill.name not in self._loaded_skill_names:
                self._loaded_skill_names.append(skill.name)
            await self._append_block(UserBlock(f"Loaded skill: {skill.name}"))
            self._update_status(f"Loaded skill {skill.name}")
            return True
        if action == "show":
            if not name:
                await self._append_block(ErrorBlock("Usage: /skills show NAME"))
                return True
            skill = find_skill(self.project_root, name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {name}"))
                return True
            await self._append_block(
                UserBlock(
                    f"Skill: {skill.name}\n"
                    f"Description: {skill.description or '(no description)'}\n"
                    f"Scope: {skill.scope}\n"
                    f"Path: {skill.path.parent}"
                )
            )
            return True
        return False

    @on(PromptTextArea.SuggestionAccepted)
    def on_suggestion_accepted(self, event: PromptTextArea.SuggestionAccepted) -> None:
        event.stop()
        self.query_one(PromptPanel).accept_first_suggestion()

    @work(exclusive=True)
    async def run_model_turn(self, prompt: str, skill_names: list[str]) -> None:
        try:
            summary = await self.run_once(
                prompt,
                project_root=self.project_root,
                settings=self.settings,
                emit_event=lambda event: self.post_message(StreamEventMessage(event)),
                should_interrupt=lambda: self.state.interrupt_requested,
                session_id=self.state.session_id,
                skill_names=skill_names,
            )
        except Exception as exc:
            self.post_message(TurnFailedMessage(exc))
            return
        self.post_message(TurnCompleteMessage(summary))

    @on(StreamEventMessage)
    async def on_stream_event(self, message: StreamEventMessage) -> None:
        message.stop()
        await self._handle_stream_event(message.event)

    @on(TurnCompleteMessage)
    async def on_turn_complete(self, message: TurnCompleteMessage) -> None:
        message.stop()
        summary = message.summary
        await self._flush_assistant_block()
        self.state = set_session_id(self.state, summary.session_id)
        self.state = set_usage(self.state, summary.usage)
        self.state = set_pending_questions(self.state, summary.pending_questions)
        self.state = set_busy(self.state, False, "Idle")
        self.state = reset_turn_buffers(self.state)
        if summary.pending_questions:
            await self._append_block(UserBlock(f"Questions pending: {len(summary.pending_questions)}"))
        await self._append_block(UsageLine(format_usage_line(summary.usage)))
        self._update_status("Idle")

    @on(TurnFailedMessage)
    async def on_turn_failed(self, message: TurnFailedMessage) -> None:
        message.stop()
        self.state = set_busy(self.state, False, "Error")
        await self._append_block(ErrorBlock(str(message.error)))
        self._update_status("Error")

    async def _handle_stream_event(self, event: DeepyStreamEvent) -> None:
        if event.kind == "text_delta" and event.text:
            self.state = add_assistant_delta(self.state, event.text)
            if self._assistant_block is not None:
                self._assistant_block.update_markdown(self.state.assistant_buffer)
                self._scroll_transcript_to_end()
            return
        if event.kind == "message" and event.text:
            if not self.state.assistant_buffer:
                self.state = add_assistant_delta(self.state, event.text)
                if self._assistant_block is not None:
                    self._assistant_block.update_markdown(self.state.assistant_buffer)
                    self._scroll_transcript_to_end()
            return
        if event.kind == "reasoning_delta" and event.text:
            self.state = add_reasoning_delta(self.state, event.text)
            if self._thinking_block is None:
                self._thinking_block = ThinkingBlock(event.text)
                await self._append_block(self._thinking_block)
            else:
                self._thinking_block.update_text(self._thinking_block.body + event.text)
                self._scroll_transcript_to_end()
            self._update_status("Thinking")
            return
        if event.kind == "tool_call":
            self._thinking_block = None
            call_id = str(event.payload.get("call_id") or "")
            block = ToolBlock.from_call(
                event.name or "tool",
                str(event.payload.get("arguments") or ""),
                call_id=call_id,
            )
            if call_id:
                self._tool_blocks[call_id] = block
            await self._append_block(block)
            self._update_status(f"Tool {event.name or 'tool'}")
            return
        if event.kind == "tool_output":
            self._thinking_block = None
            call_id = str(event.payload.get("call_id") or "")
            view = parse_tool_output(event.text)
            block = self._tool_blocks.get(call_id)
            if block is None:
                block = ToolBlock.from_output(view, call_id=call_id)
                if call_id:
                    self._tool_blocks[call_id] = block
                await self._append_block(block)
            else:
                block.update_from_output(view)
                self._scroll_transcript_to_end()
            diff_view = diff_view_from_tool_output(event.text)
            if diff_view is not None:
                await self._append_block(
                    DiffBlock(
                        diff_view,
                        theme=self.settings.ui.theme,
                        width=max(40, self.size.width - 6),
                    )
                )
            self._update_status(view.status.title())
            return
        if event.kind == "usage":
            self.state = set_usage(self.state, event.payload.get("usage"))
            return
        if event.kind == "status" and event.text:
            await self._append_block(UserBlock(event.text))
            self._update_status(event.text)

    async def _append_block(self, block: Any) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        await transcript.mount(block)
        self._scroll_transcript_to_end()

    async def _flush_assistant_block(self) -> None:
        if not self.state.assistant_buffer:
            return
        if self._assistant_block is None:
            self._assistant_block = AssistantBlock(self.state.assistant_buffer)
            await self._append_block(self._assistant_block)
            return
        self._assistant_block.update_markdown(self.state.assistant_buffer)
        self._scroll_transcript_to_end()

    def _scroll_transcript_to_end(self) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        transcript.scroll_end(animate=False, force=True, x_axis=False)
        self.call_after_refresh(self._scroll_transcript_to_end_now)
        self.set_timer(0.05, self._scroll_transcript_to_end_now)

    def _scroll_transcript_to_end_now(self) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        transcript.scroll_end(animate=False, force=True, immediate=True, x_axis=False)

    def _update_status(self, status: str) -> None:
        self.state = set_status(self.state, status)
        self.query_one(StatusBar).update_status(status)
        self.query_one("#side-status", Static).update(
            f"Project: {self.project_root}\n"
            f"Model: {self.settings.model.name}\n"
            f"Reasoning: {self.settings.model.reasoning_mode}\n"
            f"Session: {self.state.session_id or 'new'}"
        )

    def action_confirm_quit(self) -> None:
        if self.state.quit_confirm_pending:
            self.exit()
            return
        self.state = set_quit_confirm(self.state, True)
        self._update_status("Press Ctrl+D again to exit")
        self.set_timer(2.0, self._clear_quit_confirm)

    def _clear_quit_confirm(self) -> None:
        if self.state.quit_confirm_pending:
            self.state = set_quit_confirm(self.state, False)
            self._update_status("Idle" if not self.state.busy else "Running")

    def action_interrupt_or_focus_prompt(self) -> None:
        if self.state.busy:
            self.state = request_interrupt(self.state)
            self._update_status("Interrupt requested")
            return
        self.query_one("#prompt-input", PromptTextArea).focus()

    def action_focus_next_block(self) -> None:
        blocks = list(self.query(".transcript-block"))
        if not blocks:
            return
        self._focused_block_index = min(len(blocks) - 1, self._focused_block_index + 1)
        blocks[self._focused_block_index].focus()

    def action_focus_previous_block(self) -> None:
        blocks = list(self.query(".transcript-block"))
        if not blocks:
            return
        if self._focused_block_index == -1:
            self._focused_block_index = len(blocks) - 1
        else:
            self._focused_block_index = max(0, self._focused_block_index - 1)
        blocks[self._focused_block_index].focus()

    def action_toggle_help_panel(self) -> None:
        panel = self.query_one("#side-panel", Vertical)
        panel.toggle_class("-visible")
