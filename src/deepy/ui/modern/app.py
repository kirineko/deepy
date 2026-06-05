from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Label, Static

from deepy.audit import AuditModeState, AuditPolicy
from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings
from deepy.input_suggestions import InputSuggestionController
from deepy.llm.multimodal import (
    PromptImageAttachment,
    format_user_prompt_display,
    supports_image_input,
)
from deepy.llm.runner import RunSummary
from deepy.mcp import DeepyMcpRuntime
from deepy.prompts.init_agents import build_agents_init_prompt
from deepy.sessions import SessionEntry
from deepy.skills import find_skill
from deepy.ui import parse_slash_command
from deepy.ui.modern import app_bindings
from deepy.ui.modern.app_commands import AppCommandsMixin
from deepy.ui.modern.app_helpers import (
    _build_tui_status_context,
    _format_tui_side_status,
    _transcript_block_copy_text,
)
from deepy.ui.modern.app_interaction import AppInteractionMixin
from deepy.ui.modern.app_sessions import AppSessionsMixin
from deepy.ui.modern.app_skills import AppSkillsMixin
from deepy.ui.modern.app_status import AppStatusMixin
from deepy.ui.modern.app_streaming import AppStreamingMixin
from deepy.ui.modern.app_transcript import AppTranscriptMixin
from deepy.ui.modern.app_styles import APP_CSS
from deepy.ui.modern.app_widgets import StreamEventMessage, TurnCompleteMessage, TurnFailedMessage, TranscriptScroll
from deepy.ui.modern.commands import UNSUPPORTED_TUI_COMMANDS, DeepyCommandProvider
from deepy.ui.modern.render.status_format import _is_light_tui_theme
from deepy.ui.modern.screens import SkillManagementScreen
from deepy.ui.modern.state import (
    TuiController,
    TuiState,
    request_interrupt,
    reset_turn_buffers,
    set_busy,
    set_quit_confirm,
)
from deepy.ui.modern.theme import textual_theme_for_ui_theme
from deepy.ui.modern.widgets import (
    AssistantBlock,
    AuditDecisionBlock,
    ErrorBlock,
    InfoBlock,
    InlineChoiceBlock,
    LocalCommandBlock,
    PromptPanel,
    PromptTextArea,
    QuestionBlock,
    StatusBar,
    ThinkingBlock,
    ToolBlock,
    UserBlock,
)
from deepy.ui.shared.input.image_input import ImageAttachmentController
from deepy.ui.shared.input.slash_commands import (
    build_slash_commands,
    build_subagent_slash_prompt,
    is_builtin_slash_command,
    is_subagent_slash_command,
)
from deepy.ui.shared.local_command import parse_local_command

# Re-exports for tests that monkeypatch through deepy.ui.modern.app.
DeepySessionManager = app_bindings.DeepySessionManager
discover_skills = app_bindings.discover_skills
estimate_tokens_for_text = app_bindings.estimate_tokens_for_text
fetch_deepseek_balance = app_bindings.fetch_deepseek_balance
install_market_skill = app_bindings.install_market_skill
list_installed_skills = app_bindings.list_installed_skills
list_session_entries = app_bindings.list_session_entries
load_mcp_config = app_bindings.load_mcp_config
run_local_command = app_bindings.run_local_command
search_market_skills = app_bindings.search_market_skills
shell_tool_result_json = app_bindings.shell_tool_result_json
uninstall_market_skill = app_bindings.uninstall_market_skill
update_market_skill = app_bindings.update_market_skill

__all__ = [
    "DeepyTuiApp",
    "DeepySessionManager",
    "_build_tui_status_context",
    "_format_tui_side_status",
    "discover_skills",
    "list_installed_skills",
    "list_session_entries",
    "run_local_command",
    "search_market_skills",
    "uninstall_market_skill",
]

RunOnce = Callable[..., Coroutine[Any, Any, RunSummary]]


class DeepyTuiApp(
    AppCommandsMixin,
    AppSessionsMixin,
    AppSkillsMixin,
    AppStreamingMixin,
    AppTranscriptMixin,
    AppInteractionMixin,
    AppStatusMixin,
    App[None],
):
    """Experimental Textual UI for Deepy."""

    TITLE = "Deepy Modern UI"
    SUB_TITLE = "Textual"
    COMMANDS = {DeepyCommandProvider}
    BINDINGS = [
        Binding("ctrl+d", "confirm_quit", "Quit", priority=True),
        Binding("escape", "interrupt_or_focus_prompt", "Interrupt"),
        Binding("ctrl+c,super+c", "copy_focused_block", "Copy", show=False),
        Binding("ctrl+o", "toggle_help_panel", "Panel"),
        Binding("shift+tab", "cycle_audit_mode", "Audit", priority=True),
        Binding("alt+up", "focus_previous_block", "Previous block"),
        Binding("alt+down", "focus_next_block", "Next block"),
    ]
    CSS = APP_CSS

    state: var[TuiState] = var(TuiState())

    def __init__(
        self,
        *,
        settings: Settings,
        project_root: Path,
        run_once: RunOnce,
        guide_missing_config: bool = False,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.project_root = project_root
        self.run_once = run_once
        self.guide_missing_config = guide_missing_config
        self.controller = TuiController(settings=settings)
        self.audit_state = AuditModeState(settings.audit.mode)
        self.input_suggestions = InputSuggestionController(
            enabled=settings.ui.input_suggestions_enabled
        )
        self.image_attachments = ImageAttachmentController(
            supports_image_input=supports_image_input(settings)
        )
        self._assistant_block: AssistantBlock | None = None
        self._assistant_rendered_text = ""
        self._thinking_block: ThinkingBlock | None = None
        self._tool_blocks: dict[str, ToolBlock | LocalCommandBlock] = {}
        self._retryable_tool_blocks: dict[tuple[str, str], ToolBlock] = {}
        self._focused_block_index = -1
        self._pending_question_answers: OrderedDict[str, str] = OrderedDict()
        self._new_output_available = False
        self._todo_text = ""
        self._stream_tokens = 0
        self._local_command_sequence = 0
        self._status_session_entry: SessionEntry | None = None
        self._status_session_entry_id: str | None = None
        self._status_session_entry_loaded = False
        self.background_tasks = BackgroundTaskManager()
        self.mcp_runtime = DeepyMcpRuntime(
            settings,
            project_root=project_root,
            audit_policy=AuditPolicy(lambda: self.audit_state.mode, settings.audit),
        )
        self.exit_summary_text: str | None = None
        self._pending_session_cost_start: dict[str, Any] | None = None
        self._pending_audit_decision: asyncio.Future[str] | None = None
        self._pending_inline_choice: asyncio.Future[str | None] | None = None
        self._active_interaction_block: Widget | None = None
        self._approved_preflight_diffs: set[str] = set()
        self._suppressed_approval_tool_call_ids: set[str] = set()
        self._completed_tool_call_ids: set[str] = set()

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            yield TranscriptScroll(id="transcript")
            with Vertical(id="side-panel"):
                yield Label("Status", classes="block-title")
                yield Static("", id="side-status")
        yield Vertical(id="interaction-sheet")
        yield StatusBar(id="status-bar")
        yield PromptPanel(
            build_slash_commands(discover_skills(self.project_root)),
            self.project_root,
            image_attachments=self.image_attachments,
            id="prompt-panel",
        )

    async def on_mount(self) -> None:
        self._apply_theme()
        await self.query_one("#transcript", VerticalScroll).mount(
            InfoBlock(
                "Deepy Modern UI. Press Ctrl+O for status, Enter to send, "
                "Ctrl+J for newline, Ctrl+D twice to exit."
            )
        )
        self._scroll_transcript_to_end(force=True)
        self.query_one("#prompt-input", PromptTextArea).focus()
        self._refresh_status_session_entry()
        self._update_status("Idle")
        if self.guide_missing_config and not self.settings.model.api_key:
            self.call_after_refresh(self._start_initial_setup)
        self.run_worker(
            self._connect_mcp_runtime(),
            name="mcp-startup",
            group="mcp-startup",
            exclusive=False,
        )

    async def _connect_mcp_runtime(self) -> None:
        await self.mcp_runtime.connect()

    def _apply_theme(self) -> None:
        self.theme = textual_theme_for_ui_theme(
            self.settings.ui.theme,
            self.settings.ui.textual_theme,
        )
        self.screen.set_class(_is_light_tui_theme(self.settings.ui.theme, self.theme), "-light-theme")

    def _start_initial_setup(self) -> None:
        self.run_worker(self._initial_setup_command(), exclusive=False)

    async def _initial_setup_command(self) -> None:
        await self._append_block(InfoBlock("Deepy needs a provider API key before starting TUI."))
        await self._reset_command()

    @on(PromptTextArea.Submitted)
    async def on_prompt_submitted(self, event: PromptTextArea.Submitted) -> None:
        event.stop()
        if self._active_interaction_block is not None:
            self._refocus_active_interaction()
            return
        self._clear_input_suggestion()
        if self.state.busy:
            self.notify("Deepy is still working.", severity="warning")
            return
        image_attachments = list(event.image_attachments)
        local_command = parse_local_command(event.text) if not image_attachments else None
        if local_command is not None:
            await self._handle_local_command(local_command)
            return
        if not image_attachments and await self._handle_prompt_command(event.text):
            return
        self.controller.add_prompt_history(event.text)
        await self._append_block(UserBlock(format_user_prompt_display(event.text, image_attachments)))
        self._scroll_transcript_to_end(force=True)
        self._start_model_turn(
            event.text,
            list(self.controller.loaded_skill_names),
            status="Running",
            image_attachments=image_attachments,
        )

    @on(PromptTextArea.ImagePasteNotice)
    async def on_prompt_image_paste_notice(self, event: PromptTextArea.ImagePasteNotice) -> None:
        event.stop()
        await self._append_block(AssistantBlock(event.text))
        self._scroll_transcript_to_end(force=True)

    async def _handle_prompt_command(self, text: str) -> bool:
        slash = parse_slash_command(text)
        if slash is None:
            return False
        if slash.name in {"exit", "quit"}:
            self._exit_with_summary()
            return True
        await self._record_slash_command_invocation(text)
        if slash.name in UNSUPPORTED_TUI_COMMANDS:
            await self._append_block(ErrorBlock(UNSUPPORTED_TUI_COMMANDS[slash.name]))
            return True
        if slash.name == "init":
            request = build_agents_init_prompt(self.project_root, extra_instruction=slash.argument)
            self._start_model_turn(request, list(self.controller.loaded_skill_names), status="Initializing AGENTS.md")
            return True
        if is_subagent_slash_command(slash.name):
            request = build_subagent_slash_prompt(slash.name, slash.argument)
            self._start_model_turn(
                request,
                list(self.controller.loaded_skill_names),
                status=f"Using subagent {slash.name}",
            )
            return True
        if slash.name in {
            "help",
            "status",
            "mcp",
            "new",
            "sessions",
            "resume",
            "compact",
            "theme",
            "ui",
            "model",
            "view",
            "input-suggestion",
            "reset",
            "ps",
            "stop",
        }:
            self.invoke_tui_command(slash.name, slash.argument)
            return True
        if slash.name == "skills":
            self.invoke_tui_command("skills", slash.argument)
            return True
        if slash.name.startswith("skill:") or not is_builtin_slash_command(slash.name):
            skill_name = (
                slash.name.removeprefix("skill:")
                if slash.name.startswith("skill:")
                else slash.name
            )
            skill = find_skill(self.project_root, skill_name)
            if skill is None:
                if slash.name.startswith("skill:"):
                    await self._append_block(ErrorBlock(f"Skill not found: {skill_name}"))
                else:
                    await self._append_block(ErrorBlock(f"Unsupported TUI command: /{slash.name}"))
                return True
            request = slash.argument or f"Use the {skill.name} skill."
            self._start_model_turn(request, [skill.name], status=f"Using skill {skill.name}")
            return True
        await self._append_block(ErrorBlock(f"Unsupported TUI command: /{slash.name}"))
        return True

    async def _record_slash_command_invocation(self, text: str) -> None:
        self.controller.add_prompt_history(text)
        await self._append_block(UserBlock(text))
        self._scroll_transcript_to_end(force=True)

    def _start_model_turn(
        self,
        prompt: str,
        skill_names: list[str],
        *,
        status: str,
        image_attachments: list[PromptImageAttachment] | None = None,
    ) -> None:
        self._clear_input_suggestion()
        self._pending_session_cost_start = self._capture_session_cost_start()
        self.state = set_busy(reset_turn_buffers(self.state), True, status)
        self._assistant_block = None
        self._assistant_rendered_text = ""
        self._thinking_block = None
        self._stream_tokens = 0
        self._tool_blocks.clear()
        self._suppressed_approval_tool_call_ids.clear()
        self._completed_tool_call_ids.clear()
        self._update_status(status)
        self.run_model_turn(prompt, skill_names, image_attachments=image_attachments or [])

    def invoke_tui_command(self, name: str, argument: str = "") -> None:
        self.run_worker(self._run_tui_command(name, argument), exclusive=False)

    def _refresh_prompt_commands(self) -> None:
        panel = self.query_one(PromptPanel)
        panel.slash_commands = build_slash_commands(
            discover_skills(self.project_root),
            self.controller.loaded_skill_names,
        )
        prompt = self.query_one("#prompt-input", PromptTextArea)
        panel.refresh_suggestions(prompt.text)

    @on(PromptTextArea.SuggestionAccepted)
    def on_suggestion_accepted(self, event: PromptTextArea.SuggestionAccepted) -> None:
        event.stop()
        self.query_one(PromptPanel).accept_selected_suggestion()

    @on(PromptTextArea.HistoryPrevious)
    def on_history_previous(self, event: PromptTextArea.HistoryPrevious) -> None:
        event.stop()
        if self._active_interaction_block is not None:
            self._refocus_active_interaction()
            return
        prompt = self.query_one("#prompt-input", PromptTextArea)
        previous = self.controller.previous_prompt(prompt.text)
        if previous is None:
            return
        prompt.text = previous
        prompt.move_cursor((0, len(prompt.text)))

    @on(PromptTextArea.HistoryNext)
    def on_history_next(self, event: PromptTextArea.HistoryNext) -> None:
        event.stop()
        if self._active_interaction_block is not None:
            self._refocus_active_interaction()
            return
        prompt = self.query_one("#prompt-input", PromptTextArea)
        next_prompt = self.controller.next_prompt()
        if next_prompt is None:
            return
        prompt.text = next_prompt
        prompt.move_cursor((0, len(prompt.text)))

    @work(exclusive=True)
    async def run_model_turn(
        self,
        prompt: str,
        skill_names: list[str],
        image_attachments: list[PromptImageAttachment] | None = None,
    ) -> None:
        await super().run_model_turn(prompt, skill_names, image_attachments=image_attachments or [])

    @on(StreamEventMessage)
    async def on_stream_event(self, message: StreamEventMessage) -> None:
        await super().on_stream_event(message)

    @on(TurnCompleteMessage)
    async def on_turn_complete(self, message: TurnCompleteMessage) -> None:
        await super().on_turn_complete(message)

    @on(TurnFailedMessage)
    async def on_turn_failed(self, message: TurnFailedMessage) -> None:
        await super().on_turn_failed(message)

    @on(AuditDecisionBlock.Decided)
    def on_audit_decision(self, message: AuditDecisionBlock.Decided) -> None:
        super().on_audit_decision(message)

    @on(InlineChoiceBlock.Chosen)
    def on_inline_choice(self, message: InlineChoiceBlock.Chosen) -> None:
        super().on_inline_choice(message)

    @on(QuestionBlock.Answered)
    async def on_question_answered(self, message: QuestionBlock.Answered) -> None:
        await super().on_question_answered(message)

    @on(QuestionBlock.Cancelled)
    async def on_question_cancelled(self, message: QuestionBlock.Cancelled) -> None:
        await super().on_question_cancelled(message)

    @on(SkillManagementScreen.ActionRequested)
    async def on_skill_management_action(self, event: SkillManagementScreen.ActionRequested) -> None:
        await super().on_skill_management_action(event)

    def action_cycle_audit_mode(self) -> None:
        mode = self.audit_state.cycle()
        self._update_status(f"Audit {mode.value}")

    def action_confirm_quit(self) -> None:
        if self.state.quit_confirm_pending:
            self._exit_with_summary()
            return
        self.state = set_quit_confirm(self.state, True)
        self._update_status("Press Ctrl+D again to exit")
        self.set_timer(2.0, self._clear_quit_confirm)

    def action_interrupt_or_focus_prompt(self) -> None:
        if self._cancel_active_interaction():
            return
        if self.state.busy:
            self.state = request_interrupt(self.state)
            self._update_status("Interrupt requested")
            return
        prompt = self.query_one("#prompt-input", PromptTextArea)
        prompt.prepare_clear_on_next_delete()
        prompt.focus()

    def action_copy_focused_block(self) -> None:
        block = self._focused_transcript_block()
        if block is None:
            self._update_status("Focus a transcript block to copy")
            return
        text = _transcript_block_copy_text(block).strip()
        if not text:
            self._update_status("Nothing to copy")
            return
        self.copy_to_clipboard(text)
        self._update_status("Copied transcript block")

    def _focused_transcript_block(self) -> Widget | None:
        node = self.focused
        while isinstance(node, Widget):
            if node.has_class("transcript-block"):
                return node
            parent = node.parent
            node = parent if isinstance(parent, Widget) else None
        return None

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

