from __future__ import annotations

import asyncio
import shutil
import time
from collections import OrderedDict
from collections.abc import Callable, Coroutine, Sequence
from pathlib import Path
from typing import Any, Literal

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import var
from textual.widget import Widget
from textual.widget import MountError
from textual.widgets import Label, Static

from deepy.audit import ApprovalDecision, AuditModeState, AuditPolicy, PendingApproval
from deepy.background_tasks import BackgroundTaskManager, BackgroundTaskSnapshot
from deepy.config import (
    PROVIDER_CATALOG,
    Settings,
    allows_custom_model_for_provider,
    default_base_url_for_provider,
    default_model_for_provider,
    is_supported_model_for_provider,
    is_supported_provider,
    is_valid_thinking_mode_for_provider,
    is_valid_ui_theme,
    load_settings,
    provider_info_for,
    update_config_input_suggestions_enabled,
    update_config_model_settings,
    update_config_theme,
    update_config_textual_theme,
    update_config_ui_interface,
    update_config_view_mode,
    UI_SETUP_OPTIONS,
    ui_setup_from_selection,
    write_config,
)
from deepy.input_suggestions import (
    InputSuggestionController,
    generate_input_suggestion,
    is_eligible_for_input_suggestion,
)
from deepy.llm.context import estimate_tokens_for_text
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.multimodal import (
    PromptImageAttachment,
    format_user_prompt_display,
    redacted_content_text,
    supports_image_input,
)
from deepy.llm.runner import RunSummary
from deepy.mcp import DeepyMcpRuntime, format_mcp_status, load_mcp_config
from deepy.prompts.init_agents import build_agents_init_prompt
from deepy.prompts.rules import has_agents_instructions
from deepy.sessions import DeepySession, SessionEntry, list_session_entries
from deepy.session_cost import balance_snapshot_to_dict, should_track_session_cost, supports_session_cost
from deepy.sessions.manager import DeepySessionManager
from deepy.skill_market import (
    InstalledSkill,
    MarketSkill,
    install_market_skill,
    list_installed_skills,
    search_market_skills,
    uninstall_market_skill,
    update_market_skill,
)
from deepy.skills import (
    SkillInfo,
    discover_skills,
    find_skill,
    format_skills_for_terminal,
    read_skill_body,
)
from deepy.status import (
    BalanceStatus,
    build_status_report,
    fetch_deepseek_balance,
    format_balance_status,
    format_status_report,
)
from deepy.tui.commands import (
    UNSUPPORTED_TUI_COMMANDS,
    DeepyCommandProvider,
    command_catalog_markdown,
)
from deepy.tui.diff import diff_view_from_tool_output
from deepy.tui.screens import (
    Choice,
    ChoiceScreen,
    InfoScreen,
    ResetConfigResult,
    SkillManagementScreen,
    SkillScreenAction,
    SkillScreenEntry,
    TextInputScreen,
)
from deepy.tui.state import (
    TuiController,
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
from deepy.tui.theme import (
    TUI_TEXTUAL_THEME_OPTIONS,
    is_supported_textual_theme,
    textual_theme_for_ui_theme,
    textual_theme_option,
)
from deepy.tui.widgets import (
    AuditDecisionBlock,
    AssistantBlock,
    DiffBlock,
    ErrorBlock,
    InfoBlock,
    InlineChoiceBlock,
    InlineChoiceOption,
    LocalCommandBlock,
    PromptPanel,
    PromptTextArea,
    StatusBar,
    ThinkingBlock,
    ToolBlock,
    UserBlock,
    QuestionBlock,
)
from deepy.ui.ask_user_question import (
    format_ask_user_question_answers,
    format_ask_user_question_decline,
    normalize_questions,
)
from deepy.ui.exit_summary import build_exit_summary_text
from deepy.ui import parse_slash_command
from deepy.ui.local_command import (
    LocalCommandInput,
    build_synthetic_shell_transcript_items,
    parse_local_command,
    run_local_command,
    shell_tool_result_json,
)
from deepy.ui.image_input import ImageAttachmentController
from deepy.ui.message_view import parse_tool_output
from deepy.ui.session_list import format_session_title
from deepy.ui.session_picker import ResumeSessionPreview, format_session_time
from deepy.ui.slash_commands import build_slash_commands
from deepy.ui.slash_commands import build_subagent_slash_prompt
from deepy.ui.slash_commands import is_builtin_slash_command
from deepy.ui.slash_commands import is_subagent_slash_command
from deepy.ui.model_picker import provider_api_key_reconfiguration_message, thinking_mode_choices
from deepy.ui.welcome import format_home_relative_path
from deepy.usage import context_window_usage, format_usage_line
from deepy.llm.cache_context import format_cache_hit_rate, format_cache_usage
from deepy.utils import json as json_utils


RunOnce = Callable[..., Coroutine[Any, Any, RunSummary]]

_LIGHT_TEXTUAL_THEMES = {"solarized-light", "catppuccin-latte", "atom-one-light"}


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


class TranscriptScroll(VerticalScroll):
    _WHEEL_SCROLL_LINES = 4

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.prevent_default()
        event.stop()
        self.scroll_relative(
            y=max(1, abs(event.delta_y)) * self._WHEEL_SCROLL_LINES,
            animate=False,
            force=True,
            immediate=True,
        )

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.prevent_default()
        event.stop()
        self.scroll_relative(
            y=-max(1, abs(event.delta_y)) * self._WHEEL_SCROLL_LINES,
            animate=False,
            force=True,
            immediate=True,
        )


class DeepyTuiApp(App[None]):
    """Experimental Textual UI for Deepy."""

    TITLE = "Deepy Modern UI"
    SUB_TITLE = "Textual"
    COMMANDS = {DeepyCommandProvider}
    BINDINGS = [
        Binding("ctrl+d", "confirm_quit", "Quit", priority=True),
        Binding("escape", "interrupt_or_focus_prompt", "Interrupt"),
        Binding("ctrl+o", "toggle_help_panel", "Panel"),
        Binding("shift+tab", "cycle_audit_mode", "Audit", priority=True),
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
        overflow-y: auto;
        scrollbar-size-vertical: 1;
    }

    #transcript * {
        link-style: none;
    }

    #side-panel {
        width: 30;
        display: none;
        background: $panel;
        padding: 0 1;
    }

    #side-panel.-visible {
        display: block;
    }

    PromptPanel {
        height: auto;
        padding: 0 1;
        background: $boost;
    }

    #prompt-input {
        height: 4;
        min-height: 4;
        max-height: 4;
        border: none;
        padding: 0;
        background: transparent;
        overflow-y: auto;
    }

    #prompt-input:focus {
        border: none;
    }

    #prompt-images {
        height: 1;
        margin: 0 1 0 1;
        color: $accent;
        display: none;
    }

    #prompt-actions {
        height: 1;
        color: $text-muted;
        display: block;
    }

    #prompt-suggestions {
        height: auto;
        max-height: 6;
        position: absolute;
        offset: 0 -6;
        width: 100%;
        display: none;
        padding: 0 1;
        layer: overlay;
        overlay: screen;
        background: $panel;
    }

    #prompt-suggestions > .option-list--option {
        padding: 0 1;
    }

    #prompt-suggestions > .option-list--option-highlighted {
        color: #ffffff !important;
        background: #414868 !important;
        text-style: bold !important;
    }

    #prompt-suggestions > .option-list--option-disabled {
        color: #7f849c !important;
    }

    #prompt-suggestions > .option-list--option-hover {
        background: #292e42 !important;
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
        margin: 0 0 0 0;
        padding: 0 1;
        border-left: none;
    }

    .transcript-block:focus {
        background: $boost;
    }

    .block-title {
        color: $text-muted;
        text-style: none;
        height: 1;
    }

    .role-line {
        height: auto;
        margin: 0;
        padding: 0;
    }

    .role-marker {
        width: 2;
        min-width: 2;
        height: 1;
        text-style: bold;
    }

    .block-body, .block-markdown, .tool-details, #side-status, #prompt-input {
        text-style: none;
    }

    .block-markdown {
        padding: 0;
        margin: 0;
        width: 1fr;
    }

    .block-markdown MarkdownBlock {
        margin: 0;
    }

    .block-markdown MarkdownTable,
    .block-markdown Table {
        margin: 0;
        padding: 0;
    }

    .block-markdown MarkdownTableCell,
    .block-markdown TableCell {
        padding: 0 1;
    }

    .user-block {
        color: $text;
    }

    .user-block .block-title {
        color: $accent;
        text-style: bold;
    }

    .user-block .block-body {
        width: 1fr;
    }

    .info-block {
        color: $text-muted;
        margin: 0;
    }

    .assistant-block {
        color: $text;
        margin: 0 0 1 0;
    }

    .assistant-block Markdown,
    .assistant-block .block-markdown {
        color: $text;
    }

    .assistant-block .block-title {
        color: $secondary;
        text-style: bold;
    }

    .assistant-block.-active .block-title {
        color: $accent;
    }

    .thinking-block {
        color: $text-muted;
        margin: 0;
    }

    .thinking-block .block-title {
        color: $warning;
        text-style: bold;
    }

    .thinking-block .block-body {
        color: $text-muted;
        width: 1fr;
    }

    .tool-block .block-title {
        color: $success;
        text-style: bold;
    }

    .tool-block.-running .block-title {
        color: $accent;
    }

    .tool-block .block-body {
        width: 1fr;
    }

    .tool-output {
        color: $text-muted;
        margin: 0 0 0 2;
    }

    .todo-block .tool-output {
        color: $text;
    }

    .tool-details {
        margin: 1 0 0 0;
        color: $text-muted;
        display: none;
    }

    .tool-block.-retryable .block-title {
        color: $warning;
    }

    .tool-block.-ok .block-title {
        color: $success;
    }

    .tool-block.-failed .block-title {
        color: $error;
    }

    .todo-block .block-title {
        color: $success;
    }

    .question-block {
        background: $boost;
        padding: 0 1;
    }

    .question-block OptionList {
        height: auto;
        max-height: 8;
        margin-top: 1;
    }

    .question-block TextArea {
        height: 3;
        margin-top: 1;
        border: tall $accent;
    }

    #interaction-sheet {
        height: auto;
        max-height: 16;
        display: none;
        background: $panel;
        border-top: solid $primary;
        padding: 1 2;
    }

    #interaction-sheet .interaction-block {
        height: auto;
        max-height: 14;
        background: transparent;
        padding: 0;
    }

    #interaction-sheet .block-title {
        color: $accent;
        text-style: bold;
    }

    #interaction-sheet OptionList {
        height: auto;
        min-height: 3;
        max-height: 10;
        margin-top: 1;
        color: #e5e7eb !important;
        background: transparent !important;
        border: none !important;
        padding: 0;
    }

    #interaction-sheet OptionList > .option-list--option {
        color: #e5e7eb !important;
        padding: 0 1;
    }

    #interaction-sheet OptionList > .option-list--option-highlighted {
        color: #ffffff !important;
        background: #414868 !important;
        text-style: bold !important;
    }

    #interaction-sheet OptionList:focus > .option-list--option-highlighted {
        color: #ffffff !important;
        background: #7aa2f7 40% !important;
        text-style: bold !important;
    }

    #interaction-sheet OptionList > .option-list--option-disabled {
        color: #7f849c !important;
    }

    #interaction-sheet OptionList > .option-list--option-hover {
        background: #292e42 !important;
    }

    #interaction-sheet .inline-choice-options {
        height: auto;
        min-height: 3;
        max-height: 10;
        margin-top: 1;
        color: #e5e7eb;
        background: transparent;
    }

    #interaction-sheet .screen-help {
        color: $text-muted;
        margin-top: 0;
    }

    Screen.-light-theme #interaction-sheet,
    Screen.-light-theme #prompt-suggestions {
        background: #fdf6e3;
        color: #073642;
    }

    Screen.-light-theme #interaction-sheet .block-title {
        color: #586e75;
    }

    Screen.-light-theme #interaction-sheet OptionList,
    Screen.-light-theme #prompt-suggestions {
        color: #073642 !important;
        background: #fdf6e3 !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option,
    Screen.-light-theme #prompt-suggestions > .option-list--option {
        color: #073642 !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option-highlighted,
    Screen.-light-theme #interaction-sheet OptionList:focus > .option-list--option-highlighted,
    Screen.-light-theme #prompt-suggestions > .option-list--option-highlighted {
        color: #fdf6e3 !important;
        background: #268bd2 !important;
        text-style: bold !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option-disabled,
    Screen.-light-theme #prompt-suggestions > .option-list--option-disabled {
        color: #93a1a1 !important;
    }

    Screen.-light-theme #interaction-sheet OptionList > .option-list--option-hover,
    Screen.-light-theme #prompt-suggestions > .option-list--option-hover {
        background: #eee8d5 !important;
    }

    Screen.-light-theme #interaction-sheet .screen-help,
    Screen.-light-theme #interaction-sheet .inline-choice-options {
        color: #586e75;
    }

    .diff-block {
        background: transparent;
        margin: 0 0 1 0;
    }

    .error-block {
        background: transparent;
    }

    .usage-line {
        height: 1;
        margin: 0;
        padding: 0 1;
        color: $text-muted;
        display: none;
    }
    """

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
        self._update_status("Idle")
        if self.guide_missing_config and not self.settings.model.api_key:
            self.call_after_refresh(self._start_initial_setup)
        self.run_worker(self._connect_mcp_runtime(), name="mcp-startup", exclusive=False)

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

    async def _run_tui_command(self, name: str, argument: str = "") -> None:
        if name == "help":
            self.push_screen(InfoScreen("Deepy Modern UI Help", self._help_markdown()))
            return
        if name == "status":
            balance = (
                fetch_deepseek_balance(self.settings)
                if supports_session_cost(self.settings)
                else BalanceStatus(unavailable_reason="unsupported provider")
            )
            self.push_screen(
                InfoScreen(
                    "Deepy Modern UI Status",
                    self._status_markdown(balance=balance),
                )
            )
            return
        if name == "mcp":
            await self._append_block(InfoBlock(format_mcp_status(self.mcp_runtime.statuses)))
            return
        if name == "ps":
            await self._append_block(InfoBlock(_format_tui_background_tasks_transcript(self.background_tasks.list())))
            self._update_status("Background tasks listed")
            return
        if name == "stop":
            await self._stop_background_tasks(argument.strip())
            return
        if name == "new":
            await self._new_session()
            return
        if name == "sessions":
            await self._show_sessions()
            return
        if name == "resume":
            await self._resume_session(argument.strip() or None)
            return
        if name == "compact":
            await self._compact_session(argument.strip() or None)
            return
        if name == "theme":
            await self._theme_command(argument.strip())
            return
        if name == "ui":
            await self._ui_command(argument.strip())
            return
        if name == "model":
            await self._model_command(argument.strip())
            return
        if name == "view":
            await self._view_command(argument.strip())
            return
        if name == "input-suggestion":
            await self._input_suggestion_command(argument.strip())
            return
        if name == "reset":
            await self._reset_command()
            return
        if name == "skills":
            await self._handle_skills_command(argument)
            return

    def _help_markdown(self) -> str:
        return "\n\n".join(
            [
                command_catalog_markdown(),
                "## Keybindings\n"
                "- **Enter** - send prompt\n"
                "- **Ctrl+J** - insert newline\n"
                "- **Ctrl+P** - command palette\n"
                "- **Ctrl+O** - toggle side panel\n"
                "- **Shift+Tab** - cycle audit mode\n"
                "- **Alt+Up / Alt+Down** - move between transcript blocks\n"
                "- **Ctrl+Up / Ctrl+Down** - prompt history\n"
                "- **Ctrl+D twice** - exit",
                self._status_markdown(include_runtime=False),
            ]
        )

    def _status_markdown(
        self,
        *,
        include_runtime: bool = True,
        balance: BalanceStatus | None = None,
    ) -> str:
        report = build_status_report(
            self.project_root,
            self.settings,
            current_session_id=self.state.session_id,
            balance=balance,
        )
        session_cache = _format_tui_cache_status(_tui_session_entry(self.project_root, self.state.session_id))
        mcp_status = "enabled" if report.mcp.get("enabled") else "disabled"
        lines = [
            "# Status",
            "",
            "## Model",
            f"- Provider: `{report.provider}`",
            f"- Model: `{report.model}`",
            f"- Thinking: `{report.reasoning_mode}`",
            "",
            "## Runtime",
            f"- UI: `{self.settings.ui.interface}`",
            f"- Audit: `{_format_tui_audit_mode(self.audit_state, self.settings)}`",
            f"- View: `{self.settings.ui.view_mode}`",
            f"- Input suggestions: `{'enabled' if self.settings.ui.input_suggestions_enabled else 'disabled'}`",
            (
                f"- Theme: `{self.settings.ui.theme}` -> "
                f"`{textual_theme_for_ui_theme(self.settings.ui.theme, self.settings.ui.textual_theme)}`"
            ),
            "",
            "## Project",
            f"- Root: `{report.project_root}`",
            f"- Config: `{self.settings.path or 'unknown'}`",
            f"- Sessions: `{report.session_count}`",
            f"- Skills: `{report.skill_count}`",
            "",
            "## Session",
            f"- Active: `{self.state.session_id or 'new'}`",
            f"- Loaded skills: `{', '.join(self.controller.loaded_skill_names) or 'none'}`",
            f"- Session usage: `{format_usage_line(report.active_session_usage) if report.active_session_usage else 'unknown'}`",
            f"- Session cache: `{session_cache}`",
            f"- Project usage: `{format_usage_line(report.project_usage) if report.project_usage else 'unknown'}`",
            "",
            "## MCP",
            f"- State: `{mcp_status}`",
        ]
        if balance is not None:
            lines.extend(["", "## Balance", f"- Account: `{format_balance_status(balance)}`"])
        if include_runtime:
            runtime = format_status_report(report)
            if runtime:
                lines.extend(["", "## Details", "```text", runtime, "```"])
        return "\n".join(lines)

    def _background_tasks_markdown(self) -> str:
        tasks = self.background_tasks.list()
        if not tasks:
            return "# Background Tasks\n\nNo background tasks."
        lines = ["# Background Tasks", ""]
        for task in tasks:
            lines.append(f"- `{task.id}` {task.status}: `{task.command}`")
            details = _format_tui_background_task_details(task)
            if details:
                lines.append(f"  - {details}")
        return "\n".join(lines)

    async def _stop_background_tasks(self, selection: str = "") -> None:
        running_tasks = self.background_tasks.list(active_only=True)
        if not running_tasks:
            await self._append_block(InfoBlock("No running background tasks."))
            self._update_status("Idle")
            return
        target = await self._resolve_background_stop_target(running_tasks, selection)
        if target is None:
            self._update_status("Stop cancelled")
            return
        if target == "__invalid__":
            await self._append_block(ErrorBlock("Invalid background task selection."))
            self._update_status("Idle")
            return
        if target == "all":
            summary = self.background_tasks.stop_all(force_after_grace=True)
            count = len(summary.stopped)
            task_label = "task" if count == 1 else "tasks"
            await self._append_block(InfoBlock(f"Stop requested for {count} background {task_label}."))
            self._update_status("Idle")
            return
        snapshot = self.background_tasks.stop(target, force_after_grace=True)
        if snapshot is None:
            await self._append_block(ErrorBlock(f"Background task not found: {target}"))
            self._update_status("Idle")
            return
        await self._append_block(InfoBlock(f"Stop requested for background task {snapshot.id}."))
        self._update_status("Idle")

    async def _resolve_background_stop_target(
        self,
        running_tasks: Sequence[BackgroundTaskSnapshot],
        selection: str,
    ) -> str | None:
        if selection:
            return _parse_tui_background_stop_selection(running_tasks, selection)
        choices = [
            Choice(
                f"{index}. {task.id} {task.status}",
                task.id,
                task.command,
            )
            for index, task in enumerate(running_tasks, start=1)
        ]
        choices.append(
            Choice(
                f"{len(running_tasks) + 1}. all",
                "all",
                "Stop all running background tasks",
            )
        )
        choices.append(
            Choice(
                f"{len(running_tasks) + 2}. cancel",
                "cancel",
                "Return without stopping tasks",
            )
        )
        selected = await self.push_screen_wait(ChoiceScreen("Stop background task", choices))
        if not selected:
            return None
        return _parse_tui_background_stop_selection(running_tasks, selected)

    async def _new_session(self) -> None:
        self.state = set_session_id(set_pending_questions(reset_turn_buffers(self.state), []), None)
        self.controller.reset_session_state()
        self._pending_question_answers.clear()
        await self._clear_transcript()
        await self._append_block(InfoBlock("Started a new TUI session."))
        self._update_status("New session")

    async def _show_sessions(self) -> None:
        selected = await self._choose_session("Sessions")
        if selected:
            await self._resume_session(selected)

    async def _resume_session(self, session_id: str | None) -> None:
        target = session_id or await self._choose_session("Resume session")
        if not target:
            self._update_status("Resume cancelled")
            return
        entries = {entry.id for entry in list_session_entries(self.project_root)}
        if target not in entries:
            await self._append_block(ErrorBlock(f"Session not found: {target}"))
            return
        self.state = set_session_id(self.state, target)
        await self._restore_transcript(target)
        self._update_status(f"Resumed {target}")

    async def _choose_session(self, title: str) -> str | None:
        entries = list_session_entries(self.project_root)
        if not entries:
            await self._append_block(InfoBlock("No sessions found for this project."))
            return None
        choices = [await self._session_choice(entry) for entry in entries]
        return await self._choose_inline(title, choices)

    async def _session_choice(self, entry: SessionEntry) -> Choice:
        items = await _load_session_items(self.project_root, entry.id)
        preview = ResumeSessionPreview(
            id=entry.id,
            title=_session_title(items),
            status=_session_status(items),
            updated_at=entry.updated_at,
            active_tokens=entry.active_tokens,
        )
        return Choice(label=_format_tui_session_label(preview), value=entry.id)

    async def _compact_session(self, focus_instruction: str | None) -> None:
        if not self.state.session_id:
            await self._append_block(InfoBlock("No active session to compact."))
            return
        await self._append_block(InfoBlock("Compacting context..."))
        self._update_status("Compacting")
        manager = DeepySessionManager(
            project_root=self.project_root,
            settings=self.settings,
            active_session_id=self.state.session_id,
        )
        try:
            result = await manager.compact_session(
                self.state.session_id,
                focus_instruction=focus_instruction,
            )
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Compact failed: {exc}"))
            self._update_status("Compact failed")
            return
        if not result.compacted:
            await self._append_block(InfoBlock(result.message or "There is no context to compact."))
            self._update_status("Idle")
            return
        await self._append_block(
            InfoBlock(
                "Context compacted: "
                f"{result.before_tokens:,} -> {result.after_tokens:,} tokens; "
                f"preserved {result.preserved_item_count} items."
            )
        )
        self._update_status("Idle")

    async def _theme_command(self, argument: str) -> None:
        theme = argument
        if not theme:
            theme = await self._choose_inline(
                "Select theme",
                [
                    Choice(option.label, option.name, option.description)
                    for option in TUI_TEXTUAL_THEME_OPTIONS
                ],
            ) or ""
        if not theme:
            self._update_status("Theme unchanged")
            return
        theme_option = textual_theme_option(theme)
        if not is_valid_ui_theme(theme) and not is_supported_textual_theme(theme):
            choices = ", ".join(option.name for option in TUI_TEXTUAL_THEME_OPTIONS)
            await self._append_block(ErrorBlock(f"Usage: /theme <theme>\nChoices: {choices}"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist theme: config path is unknown."))
            return
        if theme_option is not None and theme_option.shared_theme is not None:
            update_config_theme(self.settings.path, theme_option.shared_theme)
            saved_message = f"Saved UI theme: {theme_option.shared_theme}"
        elif is_valid_ui_theme(theme):
            update_config_theme(self.settings.path, theme)
            saved_message = f"Saved UI theme: {theme}"
        else:
            update_config_textual_theme(self.settings.path, theme)
            saved_message = f"Saved TUI theme: {theme}"
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.input_suggestions.set_enabled(self.settings.ui.input_suggestions_enabled)
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        self._clear_input_suggestion()
        self._apply_theme()
        await self._append_block(InfoBlock(saved_message))
        self._update_status(f"Theme {self.theme}")

    async def _ui_command(self, argument: str) -> None:
        interface = argument.strip().lower()
        if not interface:
            selected = await self._choose_inline(
                "Select UI",
                [
                    Choice("classic", "classic", "Rich/prompt-toolkit terminal UI"),
                    Choice("modern", "modern", "Textual terminal UI"),
                ],
            )
            interface = selected or ""
        if not interface:
            self._update_status("UI unchanged")
            return
        if interface not in {"classic", "modern"}:
            await self._append_block(ErrorBlock("Usage: /ui classic|modern"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist UI: config path is unknown."))
            return
        update_config_ui_interface(self.settings.path, interface)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        await self._append_block(InfoBlock(f"Saved UI: {_format_tui_ui_interface_label(interface)}"))
        self._update_status("Restart Deepy to enter the selected UI")

    async def _model_command(self, argument: str) -> None:
        try:
            parts = argument.split()
            provider: str | None = None
            model: str | None = None
            reasoning: str | None = None
            if not parts:
                provider = await self._choose_inline(
                    "Select provider",
                    [
                        Choice(item.id, item.id, item.description)
                        for item in PROVIDER_CATALOG
                    ],
                    restore_prompt_focus=False,
                )
                if not provider:
                    self._update_status("Model unchanged")
                    self.query_one("#prompt-input", PromptTextArea).focus()
                    return
                model = await self._choose_inline(
                    "Select model",
                    [
                        Choice(item.name, item.name, item.description)
                        for item in provider_info_for(provider).models
                    ],
                    restore_prompt_focus=False,
                )
                if not model:
                    self._update_status("Model unchanged")
                    self.query_one("#prompt-input", PromptTextArea).focus()
                    return
                reasoning = await self._choose_inline(
                    "Select thinking",
                    [Choice(value, value, label) for value, label in thinking_mode_choices(provider)],
                    restore_prompt_focus=False,
                )
                if not reasoning:
                    self._update_status("Model unchanged")
                    self.query_one("#prompt-input", PromptTextArea).focus()
                    return
            elif parts[0] == "list" and len(parts) == 1:
                await self._append_block(InfoBlock(_model_list_text()))
                return
            elif parts[0] == "provider" and len(parts) == 2:
                provider = parts[1]
            elif parts[0] == "set" and len(parts) in {2, 3}:
                provider = "deepseek"
                model = parts[1]
                reasoning = parts[2] if len(parts) == 3 else None
            elif parts[0] == "set" and len(parts) == 4:
                provider = parts[1]
                model = parts[2]
                reasoning = parts[3]
            elif parts[0] in {"reasoning", "thinking"} and len(parts) == 2:
                reasoning = parts[1]
            else:
                await self._append_block(ErrorBlock(_model_usage_text()))
                return
            active_provider = provider or self.settings.model.provider
            if provider is not None and not is_supported_provider(provider):
                await self._append_block(ErrorBlock(f"Invalid provider: {provider}\n{_model_usage_text()}"))
                return
            if model is not None and not is_supported_model_for_provider(model, active_provider):
                await self._append_block(ErrorBlock(f"Invalid model: {model}\n{_model_usage_text()}"))
                return
            if reasoning is not None and not is_valid_thinking_mode_for_provider(reasoning, active_provider):
                await self._append_block(ErrorBlock(f"Invalid thinking mode: {reasoning}\n{_model_usage_text()}"))
                return
            if self.settings.path is None:
                await self._append_block(ErrorBlock("Cannot persist model settings: config path is unknown."))
                return
            previous_provider = self.settings.model.provider
            update_config_model_settings(
                self.settings.path,
                provider=provider,
                model=model,
                reasoning_mode=reasoning,
            )
            self.settings = load_settings(self.settings.path)
            self.controller.settings = self.settings
            self.image_attachments.supports_image_input = supports_image_input(self.settings)
            await self._append_block(
                InfoBlock(
                    "Saved model: "
                    f"{self.settings.model.provider} {self.settings.model.name} "
                    f"- thinking: {self.settings.model.reasoning_mode}"
                )
            )
            self.query_one("#prompt-input", PromptTextArea).focus()
            if self.settings.model.provider != previous_provider:
                await self._append_block(
                    InfoBlock(provider_api_key_reconfiguration_message(self.settings.model.provider))
                )
            self._update_status("Model saved")
        finally:
            self.call_after_refresh(self._focus_prompt_input)

    def _focus_prompt_input(self) -> None:
        self.query_one("#prompt-input", PromptTextArea).focus()

    async def _view_command(self, argument: str) -> None:
        argument = argument.strip().lower()
        current = self.settings.ui.view_mode
        if not argument or argument == "toggle":
            selected = "full" if current == "concise" else "concise"
        elif argument in {"concise", "full"}:
            selected = argument
        else:
            await self._append_block(ErrorBlock("Usage: /view [toggle|concise|full]"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist view mode: config path is unknown."))
            return
        update_config_view_mode(self.settings.path, selected)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        await self._append_block(InfoBlock(_format_view_mode_confirmation(self.settings.ui.view_mode)))
        self._update_status("View updated")

    async def _input_suggestion_command(self, argument: str) -> None:
        if argument:
            await self._append_block(ErrorBlock("Usage: /input-suggestion"))
            return
        if self.settings.path is None:
            await self._append_block(
                ErrorBlock("Cannot persist input suggestion setting: config path is unknown.")
            )
            return
        enabled = not self.settings.ui.input_suggestions_enabled
        update_config_input_suggestions_enabled(self.settings.path, enabled)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.input_suggestions.set_enabled(self.settings.ui.input_suggestions_enabled)
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        self._clear_input_suggestion()
        await self._append_block(
            InfoBlock(
                "Input suggestions "
                f"{'enabled' if self.settings.ui.input_suggestions_enabled else 'disabled'}."
            )
        )
        self._update_status("Input suggestions toggled")

    async def _reset_command(self) -> None:
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot reset config: config path is unknown."))
            return
        previous_interface = "modern"
        previous_theme = self.settings.ui.theme
        result = await self._collect_reset_config()
        if result is None:
            await self._append_block(InfoBlock("Reset cancelled. Existing config left unchanged."))
            self._update_status("Reset cancelled")
            return
        error = _reset_config_validation_error(result)
        if error:
            await self._append_block(ErrorBlock(error))
            return
        try:
            if self.settings.path.exists():
                self.settings.path.unlink()
            write_config(
                self.settings.path,
                api_key=result.api_key,
                provider=result.provider,
                model=result.model,
                base_url=result.base_url,
                thinking_mode=result.thinking,
                theme=result.theme,
                interface=result.interface,
            )
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Config reset failed: {exc}"))
            return
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.image_attachments.supports_image_input = supports_image_input(self.settings)
        self._apply_theme()
        await self._append_block(InfoBlock(f"Wrote {self.settings.path}"))
        if result.interface != previous_interface or result.theme != previous_theme:
            await self._append_block(
                InfoBlock(
                    "UI selection changed to "
                    f"{_format_tui_ui_interface_label(result.interface)} {result.theme}. "
                    "Restart Deepy for the UI and theme selection to take effect."
                )
            )
        self._update_status("Config reset")

    async def _collect_reset_config(self) -> ResetConfigResult | None:
        provider = await self._choose_inline(
            "Reset: select provider",
            [
                Choice(item.id, item.id, item.description)
                for item in PROVIDER_CATALOG
            ],
            restore_prompt_focus=False,
        )
        if not provider:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        provider_info = provider_info_for(provider)
        guidance = [f"Provider selected: {provider}"]
        if provider_info.api_key_url:
            guidance.append(f"Create an API key at {provider_info.api_key_url}")
        await self._append_block(InfoBlock("\n".join(guidance)))
        api_key = await self._prompt_reset_value(
            "Reset: API key",
            placeholder=f"API key for {provider}",
            password=True,
        )
        if api_key is None:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        model = await self._choose_reset_model(provider)
        if model is None:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        base_default = (
            self.settings.model.base_url
            if self.settings.model.provider == provider
            else default_base_url_for_provider(provider)
        )
        base_url = await self._prompt_reset_value(
            "Reset: base URL",
            value=base_default,
            placeholder=default_base_url_for_provider(provider),
        )
        if base_url is None:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        thinking_default = (
            self.settings.model.reasoning_mode
            if (
                self.settings.model.provider == provider
                and is_valid_thinking_mode_for_provider(self.settings.model.reasoning_mode, provider)
            )
            else provider_info.default_thinking_mode
        )
        thinking = await self._choose_inline(
            "Reset: select thinking",
            [
                Choice(value, value, _reset_choice_description(label, default=value == thinking_default))
                for value, label in thinking_mode_choices(provider)
            ],
            restore_prompt_focus=False,
        )
        if not thinking:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        ui_selection = await self._choose_inline(
            "Reset: select UI",
            [
                Choice(
                    f"{number}. {_format_tui_ui_interface_label(interface)} {theme}",
                    number,
                    _reset_choice_description("Default" if interface == "classic" and theme == "dark" else ""),
                )
                for number, interface, theme in UI_SETUP_OPTIONS
            ],
            restore_prompt_focus=False,
        )
        if not ui_selection:
            self.call_after_refresh(self._focus_prompt_input)
            return None
        interface, theme = ui_setup_from_selection(
            ui_selection,
            default_interface=self.settings.ui.interface,
            default_theme=self.settings.ui.theme,
        )
        self.call_after_refresh(self._focus_prompt_input)
        return ResetConfigResult(
            api_key=api_key,
            provider=provider,
            model=model,
            base_url=base_url,
            thinking=thinking,
            interface=interface,
            theme=theme,
        )

    async def _choose_reset_model(self, provider: str) -> str | None:
        provider_info = provider_info_for(provider)
        model_default = (
            self.settings.model.name
            if (
                self.settings.model.provider == provider
                and is_supported_model_for_provider(self.settings.model.name, provider)
            )
            else default_model_for_provider(provider)
        )
        choices = [
            Choice(model.name, model.name, _reset_choice_description(model.description, default=model.name == model_default))
            for model in provider_info.models
        ]
        custom_value = "__custom_model__"
        if allows_custom_model_for_provider(provider):
            choices.append(
                Choice(
                    "Custom model",
                    custom_value,
                    "Paste any model name copied from the OpenRouter models page",
                )
            )
        selected = await self._choose_inline(
            "Reset: select model",
            choices,
            restore_prompt_focus=False,
        )
        if not selected:
            return None
        if selected != custom_value:
            return selected
        return await self._prompt_reset_value(
            "Reset: custom model",
            value=self.settings.model.name if self.settings.model.provider == provider else "",
            placeholder="provider/model-name",
        )

    async def _prompt_reset_value(
        self,
        title: str,
        *,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
    ) -> str | None:
        return await self.push_screen_wait(
            TextInputScreen(
                title,
                value=value,
                placeholder=placeholder,
                password=password,
            )
        )

    async def _handle_local_command(self, command_input: LocalCommandInput) -> None:
        if not command_input.command:
            await self._append_block(ErrorBlock("Usage: !<command>"))
            return
        self.controller.add_prompt_history(command_input.raw_text)
        await self._append_block(UserBlock(command_input.raw_text))
        self.state = set_busy(reset_turn_buffers(self.state), True, "Running local command")
        self._update_status("Running local command")
        self._local_command_sequence += 1
        call_id = f"deepy-local-command-{self._local_command_sequence}"
        self.run_worker(self._run_local_command(command_input, call_id=call_id), exclusive=False)

    async def _run_local_command(self, command_input: LocalCommandInput, *, call_id: str) -> None:
        try:
            result = await asyncio.to_thread(
                run_local_command,
                command_input.command,
                cwd=self.project_root,
                should_interrupt=lambda: self.state.interrupt_requested,
            )
            tool_output = shell_tool_result_json(result, output=result.display_output)
            await self._handle_stream_event(
                DeepyStreamEvent(
                    kind="tool_output",
                    text=tool_output,
                    payload={"call_id": call_id},
                )
            )
            session = (
                DeepySession.open(self.project_root, self.state.session_id)
                if self.state.session_id
                else DeepySession.create(self.project_root)
            )
            await session.add_items(
                build_synthetic_shell_transcript_items(command_input.raw_text, result, call_id=call_id)
            )
            self.state = set_session_id(self.state, session.session_id)
            self.state = set_busy(reset_turn_buffers(self.state), False, "Idle")
            self._update_status("Idle")
        except Exception as exc:
            self.state = set_busy(reset_turn_buffers(self.state), False, "Error")
            await self._append_block(ErrorBlock(f"Local command failed: {exc}"))
            self._update_status("Error")

    async def _handle_skills_command(self, argument: str) -> bool:
        action, _, rest = argument.partition(" ")
        action = action.strip().lower()
        name = rest.strip()
        if not action:
            await self._open_skill_management()
            return True
        if action == "list":
            await self._append_block(InfoBlock(format_skills_for_terminal(discover_skills(self.project_root))))
            return True
        if action == "use":
            if not name:
                await self._append_block(ErrorBlock("Usage: /skills use NAME"))
                return True
            skill = find_skill(self.project_root, name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {name}"))
                return True
            if skill.name not in self.controller.loaded_skill_names:
                self.controller.loaded_skill_names.append(skill.name)
            self._refresh_prompt_commands()
            await self._append_block(InfoBlock(f"Loaded skill: {skill.name}"))
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
            self.push_screen(InfoScreen(f"Skill: {skill.name}", _skill_detail_markdown(skill)))
            return True
        if action == "search":
            await self._skills_search(name)
            return True
        if action == "install":
            await self._skills_install(name)
            return True
        if action == "uninstall":
            await self._skills_uninstall(name)
            return True
        if action == "installed":
            await self._skills_installed()
            return True
        if action == "update":
            await self._skills_update(name)
            return True
        return False

    async def _open_skill_management(self) -> None:
        screen = SkillManagementScreen(
            _installed_skill_entries(self.project_root),
            [],
            view="market",
            market_loading=True,
        )
        self.push_screen(screen)
        self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")

    @on(SkillManagementScreen.ActionRequested)
    async def on_skill_management_action(self, event: SkillManagementScreen.ActionRequested) -> None:
        event.stop()
        action = event.action
        screen = event.screen
        if action.action == "refresh":
            screen.set_market_loading("Refreshing skill market...")
            self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")
            return
        self.run_worker(self._handle_skill_screen_action(action, screen), name="skill-management-action")

    async def _handle_skill_screen_action(
        self,
        action: SkillScreenAction,
        screen: SkillManagementScreen,
    ) -> bool:
        if action.action == "use":
            skill = find_skill(self.project_root, action.name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {action.name}"))
                return True
            if skill.name not in self.controller.loaded_skill_names:
                self.controller.loaded_skill_names.append(skill.name)
            self._refresh_prompt_commands()
            await self._append_block(InfoBlock(f"Loaded skill: {skill.name}"))
            self._update_status(f"Loaded skill {skill.name}")
            return True
        if action.action == "show":
            if action.source == "market" and find_skill(self.project_root, action.name) is None:
                entry = next((item for item in screen.market if item.name == action.name), None)
                if entry is not None:
                    await self.push_screen_wait(
                        InfoScreen(f"Market Skill: {entry.name}", _market_detail_markdown(entry))
                    )
                    return True
            skill = find_skill(self.project_root, action.name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {action.name}"))
                return True
            await self.push_screen_wait(InfoScreen(f"Skill: {skill.name}", _skill_detail_markdown(skill)))
            return True
        if action.action == "install":
            await self._skills_install_from_screen(action.name, screen=screen)
            return True
        if action.action == "uninstall":
            await self._skills_uninstall_from_screen(action.name, screen=screen)
            return True
        if action.action == "update":
            await self._skills_update(action.name)
            return True
        return False

    async def _refresh_skill_management_market(self, screen: SkillManagementScreen) -> None:
        market_entries, market_error = await self._load_market_entries()
        try:
            screen.update_installed(_installed_skill_entries(self.project_root))
            screen.update_market(market_entries, market_error=market_error)
        except RuntimeError:
            return

    async def _load_market_entries(self) -> tuple[list[SkillScreenEntry], str]:
        try:
            skills = await asyncio.to_thread(search_market_skills, "")
        except Exception as exc:
            return [], f"Skill market error: {exc}"
        local_names = {
            skill.name for skill in discover_skills(self.project_root) if skill.scope in {"project", "user"}
        }
        return [_market_skill_entry(skill, local_names=local_names) for skill in skills], ""

    async def _skills_search(self, query: str) -> None:
        try:
            skills = await asyncio.to_thread(search_market_skills, query)
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        await self._append_block(InfoBlock(_format_market_skills(skills)))

    async def _skills_install(self, name: str) -> None:
        if not name:
            await self._append_block(ErrorBlock("Usage: /skills install NAME"))
            return
        scope = await self.push_screen_wait(
            ChoiceScreen(
                "Install skill",
                [
                    Choice("user", "user", "Install into ~/.agents/skills"),
                    Choice("project", "project", "Install into this project's .agents/skills"),
                ],
            )
        )
        install_scope: Literal["user", "project"]
        if scope == "user":
            install_scope = "user"
        elif scope == "project":
            install_scope = "project"
        else:
            self._update_status("Install cancelled")
            return
        try:
            record = await asyncio.to_thread(
                install_market_skill,
                name,
                scope=install_scope,
                project_root=self.project_root,
            )
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        self._refresh_prompt_commands()
        await self._append_block(InfoBlock(f"Installed skill: {record.name} ({record.scope}) -> {record.install_path}"))
        self._update_status(f"Installed {record.name}")

    async def _skills_install_from_screen(self, name: str, *, screen: SkillManagementScreen) -> None:
        if not name:
            self._update_status("Select a skill to install")
            return
        scope = await self.push_screen_wait(
            ChoiceScreen(
                "Install skill",
                [
                    Choice("user", "user", "Install into ~/.agents/skills"),
                    Choice("project", "project", "Install into this project's .agents/skills"),
                ],
            )
        )
        install_scope: Literal["user", "project"]
        if scope == "user":
            install_scope = "user"
        elif scope == "project":
            install_scope = "project"
        else:
            self._update_status("Install cancelled")
            return
        screen.set_operation_loading(f"Installing {name}...")
        try:
            record = await asyncio.to_thread(
                install_market_skill,
                name,
                scope=install_scope,
                project_root=self.project_root,
            )
        except Exception as exc:
            self._update_status(f"Skill install failed: {exc}")
            screen.clear_operation_loading()
            return
        self._refresh_prompt_commands()
        self._update_status(f"Installed {record.name} ({record.scope})")
        screen.update_installed(_installed_skill_entries(self.project_root))
        screen.set_market_loading("Refreshing skill market...")
        self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")

    async def _skills_uninstall(self, name: str) -> None:
        if not name:
            await self._append_block(ErrorBlock("Usage: /skills uninstall NAME"))
            return
        skill = find_skill(self.project_root, name)
        if skill is not None and skill.scope == "builtin":
            await self._append_block(ErrorBlock(f"Built-in skill cannot be uninstalled: {skill.name}"))
            return
        record = next((item for item in list_installed_skills() if item.name.lower() == name.lower()), None)
        if record is None and skill is not None and skill.scope in {"project", "user"}:
            try:
                removed_path = await asyncio.to_thread(_remove_local_skill_directory, skill.path.parent)
            except Exception as exc:
                await self._append_block(ErrorBlock(f"Skill remove failed: {exc}"))
                return
            self.controller.loaded_skill_names = [
                skill_name for skill_name in self.controller.loaded_skill_names if skill_name.lower() != name.lower()
            ]
            self._refresh_prompt_commands()
            await self._append_block(InfoBlock(f"Removed local skill: {skill.name} ({skill.scope}) -> {removed_path}"))
            self._update_status(f"Removed {skill.name}")
            return
        try:
            removed = await asyncio.to_thread(uninstall_market_skill, name)
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        self.controller.loaded_skill_names = [
            skill_name for skill_name in self.controller.loaded_skill_names if skill_name.lower() != name.lower()
        ]
        self._refresh_prompt_commands()
        await self._append_block(InfoBlock(f"Uninstalled skill: {removed}"))
        self._update_status(f"Uninstalled {removed}")

    async def _skills_uninstall_from_screen(self, name: str, *, screen: SkillManagementScreen) -> None:
        if not name:
            self._update_status("Select a skill to uninstall")
            return
        skill = find_skill(self.project_root, name)
        if skill is not None and skill.scope == "builtin":
            self._update_status(f"Built-in skill cannot be uninstalled: {skill.name}")
            return
        record = next((item for item in list_installed_skills() if item.name.lower() == name.lower()), None)
        screen.set_operation_loading(f"Uninstalling {name}...")
        if record is None and skill is not None and skill.scope in {"project", "user"}:
            try:
                await asyncio.to_thread(_remove_local_skill_directory, skill.path.parent)
            except Exception as exc:
                self._update_status(f"Skill remove failed: {exc}")
                screen.clear_operation_loading()
                return
            removed_name = skill.name
        else:
            try:
                removed_name = await asyncio.to_thread(uninstall_market_skill, name)
            except Exception as exc:
                self._update_status(f"Skill uninstall failed: {exc}")
                screen.clear_operation_loading()
                return
        self.controller.loaded_skill_names = [
            skill_name for skill_name in self.controller.loaded_skill_names if skill_name.lower() != name.lower()
        ]
        self._refresh_prompt_commands()
        self._update_status(f"Uninstalled {removed_name}")
        screen.update_installed(_installed_skill_entries(self.project_root))
        screen.set_market_loading("Refreshing skill market...")
        self.run_worker(self._refresh_skill_management_market(screen), name="skill-market-refresh")

    async def _skills_installed(self) -> None:
        records = await asyncio.to_thread(list_installed_skills)
        await self._append_block(InfoBlock(_format_installed_records(records)))

    async def _skills_update(self, name: str) -> None:
        if not name:
            await self._append_block(ErrorBlock("Usage: /skills update NAME|--all"))
            return
        try:
            if name == "--all":
                records = await asyncio.to_thread(list_installed_skills)
                if not records:
                    await self._append_block(InfoBlock("No market-installed skills."))
                    return
                lines = []
                for record in records:
                    status, updated = await asyncio.to_thread(update_market_skill, record.name)
                    lines.append(f"{updated.name}: {status}")
                await self._append_block(InfoBlock("\n".join(lines)))
            else:
                status, updated = await asyncio.to_thread(update_market_skill, name)
                await self._append_block(InfoBlock(f"{updated.name}: {status}"))
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Skill market error: {exc}"))
            return
        self._refresh_prompt_commands()
        self._update_status("Skills updated")

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
        try:
            summary = await self.run_once(
                prompt,
                project_root=self.project_root,
                settings=self.settings,
                emit_event=lambda event: self.post_message(StreamEventMessage(event)),
                should_interrupt=lambda: self.state.interrupt_requested,
                session_id=self.state.session_id,
                skill_names=skill_names,
                background_tasks=self.background_tasks,
                mcp_runtime=self.mcp_runtime,
                audit_mode=self.audit_state,
                approval_resolver=self._tui_approval_resolver,
                image_attachments=image_attachments or [],
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
        self._record_pending_session_cost_start(summary.session_id)
        self.state = set_usage(self.state, summary.usage)
        self.state = set_pending_questions(self.state, summary.pending_questions)
        self.state = set_busy(self.state, False, "Idle")
        self.state = reset_turn_buffers(self.state)
        if summary.pending_questions:
            await self._show_pending_question(summary.pending_questions)
        self._update_status("Idle")
        self.run_worker(self._prepare_input_suggestion(summary), exclusive=False)

    @on(TurnFailedMessage)
    async def on_turn_failed(self, message: TurnFailedMessage) -> None:
        message.stop()
        self._pending_session_cost_start = None
        self.state = set_busy(self.state, False, "Error")
        await self._append_block(ErrorBlock(str(message.error)))
        self._update_status("Error")

    async def _tui_approval_resolver(self, pending: list[PendingApproval]) -> list[ApprovalDecision]:
        decisions: list[ApprovalDecision] = []
        for item in pending:
            if item.call_id:
                self._suppressed_approval_tool_call_ids.add(item.call_id)
            await self._detach_pending_approval_tool_block(item)
            proposed_diff = await self._append_preflight_diff(item)
            choice = await self._show_inline_audit_decision(item)
            approved = choice == "approve"
            if proposed_diff and approved:
                self._approved_preflight_diffs.add(proposed_diff)
            elif proposed_diff:
                await self._append_block(InfoBlock("Proposed change rejected."))
            elif approved:
                await self._append_pending_approval_tool_block(item)
                if item.call_id:
                    self._suppressed_approval_tool_call_ids.discard(item.call_id)
            decisions.append(
                ApprovalDecision(
                    outcome="approve" if approved else "reject",
                    rejection_message=None
                    if approved
                    else "Tool execution was rejected by the user audit approval decision.",
                )
            )
        return decisions

    async def _detach_pending_approval_tool_block(self, item: PendingApproval) -> None:
        block = self._approval_tool_block(item)
        if block is None or not isinstance(block.parent, Widget):
            return
        await block.remove()

    async def _append_pending_approval_tool_block(self, item: PendingApproval) -> None:
        if not item.call_id:
            return
        existing = self._tool_blocks.get(item.call_id)
        if isinstance(existing, LocalCommandBlock):
            return
        block = existing if isinstance(existing, ToolBlock) else None
        if block is None:
            block = ToolBlock.from_call(item.tool_name, item.arguments, call_id=item.call_id)
        self._tool_blocks[item.call_id] = block
        if block.parent is None:
            await self._append_block(block)

    def _approval_tool_block(self, item: PendingApproval) -> ToolBlock | None:
        if item.call_id:
            block = self._tool_blocks.get(item.call_id)
            return block if isinstance(block, ToolBlock) else None
        expected_arguments = ToolBlock.from_call(item.tool_name, item.arguments, call_id="").arguments
        for block in self._tool_blocks.values():
            if (
                isinstance(block, ToolBlock)
                and block.tool_name == item.tool_name
                and block.arguments == expected_arguments
            ):
                return block
        return None

    async def _append_preflight_diff(self, item: PendingApproval) -> str | None:
        if item.preflight is None:
            return None
        output = json_utils.dumps(item.preflight)
        diff_text = _tool_output_diff_text(output)
        diff_view = diff_view_from_tool_output(output, project_root=self.project_root)
        if diff_text is None or diff_view is None:
            return None
        await self._append_block(
            DiffBlock(
                diff_view,
                theme=self.settings.ui.theme,
                width=max(40, self.size.width - 6),
            )
        )
        return diff_text

    async def _show_inline_audit_decision(self, item: PendingApproval) -> str:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_audit_decision = future
        block = AuditDecisionBlock(
            item,
            project_root=self.project_root,
            width=max(40, self.size.width - 6),
        )
        await self._show_interaction_block(block)
        try:
            return await future
        finally:
            if self._pending_audit_decision is future:
                self._pending_audit_decision = None
            await self._clear_interaction_sheet()
            self.call_after_refresh(self.query_one("#prompt-input", PromptTextArea).focus)

    @on(AuditDecisionBlock.Decided)
    def on_audit_decision(self, message: AuditDecisionBlock.Decided) -> None:
        message.stop()
        future = self._pending_audit_decision
        if future is not None and not future.done():
            future.set_result(message.outcome)

    async def _choose_inline(
        self,
        title: str,
        choices: list[Choice],
        *,
        restore_prompt_focus: bool = True,
    ) -> str | None:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str | None] = loop.create_future()
        self._pending_inline_choice = future
        block = InlineChoiceBlock(
            title,
            [
                InlineChoiceOption(choice.label, choice.value, choice.description)
                for choice in choices
            ],
        )
        await self._show_interaction_block(block)
        try:
            return await future
        finally:
            if self._pending_inline_choice is future:
                self._pending_inline_choice = None
            await self._clear_interaction_sheet()
            if restore_prompt_focus:
                try:
                    prompt = self.query_one("#prompt-input", PromptTextArea)
                except NoMatches:
                    return
                self.call_after_refresh(prompt.focus)

    @on(InlineChoiceBlock.Chosen)
    def on_inline_choice(self, message: InlineChoiceBlock.Chosen) -> None:
        message.stop()
        future = self._pending_inline_choice
        if future is not None and not future.done():
            future.set_result(message.value)

    @on(QuestionBlock.Answered)
    async def on_question_answered(self, message: QuestionBlock.Answered) -> None:
        message.stop()
        self._pending_question_answers[message.question] = message.answer
        questions = normalize_questions(self.state.pending_questions)
        if len(self._pending_question_answers) < len(questions):
            await self._show_interaction_block(QuestionBlock(questions[len(self._pending_question_answers)]))
            return
        await self._clear_interaction_sheet()
        continuation = format_ask_user_question_answers(self._pending_question_answers)
        self._pending_question_answers.clear()
        self.state = set_pending_questions(self.state, [])
        self.state = set_busy(reset_turn_buffers(self.state), True, "Running")
        self._assistant_block = None
        self._assistant_rendered_text = ""
        self._thinking_block = None
        self._stream_tokens = 0
        self._tool_blocks.clear()
        self._suppressed_approval_tool_call_ids.clear()
        self._completed_tool_call_ids.clear()
        self._update_status("Running")
        self.run_model_turn(continuation, list(self.controller.loaded_skill_names))

    @on(QuestionBlock.Cancelled)
    async def on_question_cancelled(self, message: QuestionBlock.Cancelled) -> None:
        message.stop()
        await self._clear_interaction_sheet()
        self._pending_question_answers.clear()
        self.state = set_pending_questions(self.state, [])
        await self._append_block(UserBlock(format_ask_user_question_decline()))
        self._update_status("Question cancelled")

    async def _show_pending_question(self, pending_questions: list[dict[str, Any]]) -> None:
        questions = normalize_questions(pending_questions)
        if not questions:
            self._update_status(f"Questions pending: {len(pending_questions)}")
            return
        self._pending_question_answers.clear()
        await self._show_interaction_block(QuestionBlock(questions[0]))

    async def _show_interaction_block(self, block: Widget) -> None:
        sheet = self.query_one("#interaction-sheet", Vertical)
        await sheet.remove_children()
        sheet.display = True
        self._active_interaction_block = block
        self._set_prompt_interaction_locked(True)
        await sheet.mount(block)
        self._focus_interaction_block(block)
        self._scroll_transcript_to_end(force=True)
        self.call_after_refresh(lambda: self._scroll_transcript_to_end(force=True))

    async def _clear_interaction_sheet(self) -> None:
        try:
            sheet = self.query_one("#interaction-sheet", Vertical)
        except NoMatches:
            return
        await sheet.remove_children()
        sheet.display = False
        self._active_interaction_block = None
        self._set_prompt_interaction_locked(False)

    def _set_prompt_interaction_locked(self, locked: bool) -> None:
        try:
            prompt = self.query_one("#prompt-input", PromptTextArea)
        except NoMatches:
            return
        prompt.disabled = locked

    def _refocus_active_interaction(self) -> None:
        block = self._active_interaction_block
        if block is not None:
            self._focus_interaction_block(block)

    def _focus_interaction_block(self, block: Widget) -> None:
        def focus_target() -> None:
            for selector in (
                "#question-custom",
                "#inline-choice-options",
                "#audit-decision-options",
                "#question-options",
            ):
                try:
                    target = block.query_one(selector)
                except NoMatches:
                    continue
                if target.display is False:
                    continue
                target.focus()
                return
            block.focus()

        self.call_after_refresh(focus_target)

    def _cancel_active_interaction(self) -> bool:
        block = self._active_interaction_block
        if isinstance(block, AuditDecisionBlock):
            block.action_reject()
            return True
        if isinstance(block, QuestionBlock):
            block.action_cancel()
            return True
        if isinstance(block, InlineChoiceBlock):
            block.action_cancel()
            return True
        return False

    async def _prepare_input_suggestion(self, summary: RunSummary) -> None:
        self._clear_input_suggestion()
        if not summary.session_id or summary.pending_questions:
            return
        session = DeepySession.open(self.project_root, summary.session_id)
        items = await session.get_items()
        if not is_eligible_for_input_suggestion(
            items,
            enabled=self.settings.ui.input_suggestions_enabled,
            has_pending_questions=bool(summary.pending_questions),
            turn_status=summary.status,
        ):
            return
        suggestion = await generate_input_suggestion(self.settings, items)
        if suggestion is None or self.state.busy or self.state.pending_questions:
            return
        session.record_input_suggestion_usage(
            suggestion.usage,
            model=suggestion.model,
            elapsed_ms=suggestion.elapsed_ms,
        )
        self.input_suggestions.set_suggestion(suggestion.text)
        panel = self.query_one(PromptPanel)
        panel.set_input_suggestion(suggestion.text)

    def _clear_input_suggestion(self) -> None:
        self.input_suggestions.dismiss()
        try:
            self.query_one(PromptPanel).clear_input_suggestion()
        except NoMatches:
            return

    def _record_stream_progress(self, text: str) -> None:
        self._stream_tokens += estimate_tokens_for_text(text)

    def _stream_status_text(self) -> str:
        return (
            f"↓ {_format_stream_token_count_short(self._stream_tokens)} tokens"
            if self._stream_tokens > 0
            else "Running"
        )

    async def _handle_stream_event(self, event: DeepyStreamEvent) -> None:
        if event.kind == "text_delta" and event.text:
            self._record_stream_progress(event.text)
            self.state = add_assistant_delta(self.state, event.text)
            await self._append_assistant_delta(event.text)
            self._update_status(self._stream_status_text())
            return
        if event.kind == "message" and event.text:
            if not self.state.assistant_buffer:
                self.state = add_assistant_delta(self.state, event.text)
                await self._append_assistant_delta(event.text)
            return
        if event.kind == "raw_response":
            if raw_tool_call := _raw_tool_call_event(event):
                await self._handle_stream_event(raw_tool_call)
                return
            if event.text:
                self._record_stream_progress(event.text)
                self._update_status(self._stream_status_text())
            return
        if event.kind == "reasoning_delta" and event.text:
            self._record_stream_progress(event.text)
            self.state = add_reasoning_delta(self.state, event.text)
            if self.settings.ui.view_mode == "full":
                if self._thinking_block is None:
                    self._thinking_block = ThinkingBlock(event.text)
                    await self._append_block(self._thinking_block)
                else:
                    anchored = self._transcript_is_anchored_now()
                    self._thinking_block.update_text(self._thinking_block.body + event.text)
                    self._scroll_transcript_to_end(force=anchored)
            self._update_status(self._stream_status_text())
            return
        if event.kind == "tool_call":
            self._thinking_block = None
            call_id = str(event.payload.get("call_id") or "")
            if call_id and call_id in self._completed_tool_call_ids:
                return
            tool_name = event.name or "tool"
            arguments = str(event.payload.get("arguments") or "")
            params = ToolBlock.from_call(tool_name, arguments, call_id=call_id).arguments
            retry_key = _recoverable_tool_key(tool_name, params)
            block = self._retryable_tool_blocks.pop(retry_key, None) if retry_key is not None else None
            existing_block = self._tool_blocks.get(call_id) if call_id else None
            if block is None and isinstance(existing_block, ToolBlock):
                block = existing_block
            if block is not None:
                block.call_id = call_id
                block.update_from_call(tool_name, arguments)
            else:
                block = ToolBlock.from_call(tool_name, arguments, call_id=call_id)
            if call_id:
                self._tool_blocks[call_id] = block
            if call_id and call_id in self._suppressed_approval_tool_call_ids:
                self._update_status(f"Tool {event.name or 'tool'} pending approval")
                return
            if block.parent is None:
                await self._append_block(block)
            self._close_active_assistant_if_followed_by(block)
            self._update_status(f"Tool {event.name or 'tool'}")
            return
        if event.kind == "tool_output":
            self._thinking_block = None
            call_id = str(event.payload.get("call_id") or "")
            if call_id:
                self._completed_tool_call_ids.add(call_id)
                self._suppressed_approval_tool_call_ids.discard(call_id)
            view = parse_tool_output(event.text)
            block = self._tool_blocks.get(call_id)
            if _is_local_command_tool_output(view):
                local_block = LocalCommandBlock.from_output(view, call_id=call_id)
                if call_id:
                    self._tool_blocks[call_id] = local_block
                await self._replace_or_append_block(block, local_block)
                self._close_active_assistant_if_followed_by(local_block)
                self._update_status(view.status.title())
                return
            diff_view = diff_view_from_tool_output(event.text, project_root=self.project_root)
            if diff_view is not None:
                diff_text = _tool_output_diff_text(event.text)
                if diff_text is not None and diff_text in self._approved_preflight_diffs:
                    self._approved_preflight_diffs.discard(diff_text)
                    if block is not None and block.parent is not None:
                        await block.remove()
                    self._update_status(view.status.title())
                    return
                diff_block = DiffBlock(
                    diff_view,
                    theme=self.settings.ui.theme,
                    width=max(40, self.size.width - 6),
                )
                await self._replace_or_prioritize_diff_block(block, diff_block)
                self._close_active_assistant_if_followed_by(diff_block)
                self._update_status(view.status.title())
                return
            if block is None:
                block = ToolBlock.from_output(view, call_id=call_id, project_root=self.project_root)
                if call_id:
                    self._tool_blocks[call_id] = block
                await self._append_block(block)
                self._close_active_assistant_if_followed_by(block)
            elif isinstance(block, ToolBlock):
                anchored = self._transcript_is_anchored_now()
                block.update_from_output(view, project_root=self.project_root)
                self._scroll_transcript_to_end(force=anchored)
                self._close_active_assistant_if_followed_by(block)
            else:
                return
            retry_key = _recoverable_tool_key(view.name, block.arguments)
            if view.status == "retryable" and retry_key is not None:
                self._retryable_tool_blocks[retry_key] = block
            elif view.ok is True and retry_key is not None:
                self._retryable_tool_blocks.pop(retry_key, None)
            if view.name == "todo_write":
                self._todo_text = block.output_body
                self._update_status(self.state.status)
            self._update_status(view.status.title())
            return
        if event.kind == "usage":
            self.state = set_usage(self.state, event.payload.get("usage"))
            return
        if event.kind == "status" and event.text:
            await self._append_block(UserBlock(event.text))
            self._update_status(event.text)

    async def _append_block(self, block: Any) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        if not transcript.is_attached:
            return
        anchored = self._transcript_is_anchored(transcript)
        try:
            await transcript.mount(block)
        except MountError:
            return
        self._scroll_transcript_to_end(force=anchored)

    async def _replace_or_append_block(self, old_block: Widget | None, new_block: Widget) -> None:
        if old_block is None or not isinstance(old_block.parent, Widget):
            await self._append_block(new_block)
            return
        transcript = old_block.parent
        anchored = self._transcript_is_anchored_now()
        try:
            await transcript.mount(new_block, before=old_block)
        except MountError:
            await self._append_block(new_block)
            return
        await old_block.remove()
        self._scroll_transcript_to_end(force=anchored)

    async def _replace_or_prioritize_diff_block(
        self,
        old_block: Widget | None,
        new_block: Widget,
    ) -> None:
        assistant_block = self._assistant_block
        if assistant_block is not None and isinstance(assistant_block.parent, Widget):
            if old_block is None or not _widget_appears_before(old_block, assistant_block):
                await self._insert_block_before(assistant_block, new_block)
                if old_block is not None and isinstance(old_block.parent, Widget):
                    await old_block.remove()
                return
        await self._replace_or_append_block(old_block, new_block)

    async def _insert_block_before(self, anchor: Widget, block: Widget) -> None:
        parent = anchor.parent
        if not isinstance(parent, Widget):
            await self._append_block(block)
            return
        anchored = self._transcript_is_anchored_now()
        try:
            await parent.mount(block, before=anchor)
        except MountError:
            await self._append_block(block)
            return
        self._scroll_transcript_to_end(force=anchored)

    async def _clear_transcript(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        await transcript.remove_children()
        self._assistant_block = None
        self._assistant_rendered_text = ""
        self._thinking_block = None
        self._tool_blocks.clear()
        self._suppressed_approval_tool_call_ids.clear()
        self._completed_tool_call_ids.clear()
        self._focused_block_index = -1

    async def _restore_transcript(self, session_id: str) -> None:
        await self._clear_transcript()
        session = DeepySession.open(self.project_root, session_id)
        try:
            items = await session.get_items(limit=80)
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Failed to restore session: {exc}"))
            return
        await self._append_block(InfoBlock(f"Resumed session: {session_id}"))
        for item in items:
            await self._restore_transcript_item(item)

    async def _restore_transcript_item(self, item: dict[str, Any]) -> None:
        item_type = _item_type(item)
        role = _role(item)

        if item_type == "reasoning":
            text = _reasoning_text(item)
            if text.strip() and self.settings.ui.view_mode == "full":
                await self._append_block(ThinkingBlock(text))
            return

        if item_type == "function_call":
            await self._handle_stream_event(_history_tool_call_event(item))
            return

        if item_type == "function_call_output" or role == "tool":
            await self._handle_stream_event(_history_tool_output_event(item))
            return

        if role == "user":
            content = _item_text(item.get("content", item.get("output", "")))
            if content:
                await self._append_block(UserBlock(content))
            return

        if role == "assistant":
            content = _item_text(item.get("content", item.get("output", "")))
            if content.strip():
                await self._append_block(AssistantBlock(content))
            for tool_call in _chat_tool_calls(item):
                await self._handle_stream_event(_history_tool_call_event(tool_call))
            return

        content = _item_text(item.get("content", item.get("output", item.get("text", ""))))
        if content:
            await self._append_block(InfoBlock(content))

    async def _flush_assistant_block(self) -> None:
        if not self.state.assistant_buffer:
            return
        remaining = self.state.assistant_buffer[len(self._assistant_rendered_text) :]
        if remaining:
            await self._append_assistant_delta(remaining)
        if self._assistant_block is None:
            return
        self._assistant_block.set_active(False)

    async def _append_assistant_delta(self, text: str) -> None:
        if not text:
            return
        if self._assistant_block is None:
            self._assistant_block = AssistantBlock(text, active=True)
            await self._append_block(self._assistant_block)
        else:
            anchored = self._transcript_is_anchored_now()
            self._assistant_block.set_active(True)
            await self._assistant_block.update_markdown(self._assistant_block.markdown + text)
            self._scroll_transcript_to_end(force=anchored)
        self._assistant_rendered_text += text

    def _close_active_assistant_if_followed_by(self, block: Widget) -> None:
        assistant = self._assistant_block
        if assistant is None:
            return
        if not isinstance(assistant.parent, Widget) or assistant.parent is not block.parent:
            return
        if not _widget_appears_before(assistant, block):
            return
        assistant.set_active(False)
        self._assistant_block = None
        self._scroll_transcript_to_end(force=self._transcript_is_anchored_now())

    def _scroll_transcript_to_end(self, *, force: bool = False) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        if not force and not self._transcript_is_anchored(transcript):
            self._new_output_available = True
            self._set_status_bar("New output ↓")
            return
        self._new_output_available = False
        transcript.scroll_end(animate=False, force=True, x_axis=False)
        self.call_after_refresh(self._scroll_transcript_to_end_now)
        self.set_timer(0.05, self._scroll_transcript_to_end_now)

    def _scroll_transcript_to_end_now(self) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        transcript.scroll_end(animate=False, force=True, immediate=True, x_axis=False)

    def _transcript_is_anchored(self, transcript: VerticalScroll) -> bool:
        return transcript.scroll_y >= max(0, transcript.max_scroll_y - 1)

    def _transcript_is_anchored_now(self) -> bool:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return True
        return self._transcript_is_anchored(transcript)

    def _update_status(self, status: str) -> None:
        self.state = set_status(self.state, status)
        self._set_status_bar(status)
        try:
            side_status = self.query_one("#side-status", Static)
        except NoMatches:
            return
        side_status.update(
            _format_tui_side_status(
                self.project_root,
                self.settings,
                self.state.session_id,
                self.controller.loaded_skill_names,
                self._todo_text,
                audit_state=self.audit_state,
            )
        )

    def _set_status_bar(self, status: str) -> None:
        display = (
            f"{status} · New output ↓"
            if self._new_output_available and status != "New output ↓"
            else status
        )
        try:
            status_bar = self.query_one(StatusBar)
        except NoMatches:
            return
        status_bar.update_status(display, self._status_context())

    def _status_context(self) -> str:
        context = _build_tui_status_context(
            self.state.session_id,
            project_root=self.project_root,
            settings=self.settings,
            background_tasks=self.background_tasks,
            audit_state=self.audit_state,
        )
        return context

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

    def _exit_with_summary(self) -> None:
        self._record_session_cost_end()
        self.exit_summary_text = self._build_exit_summary_text()
        self._cleanup_background_tasks()
        asyncio.create_task(self.mcp_runtime.cleanup())
        self.exit()

    def _cleanup_background_tasks(self) -> None:
        self.background_tasks.stop_all(force_after_grace=True)

    def _build_exit_summary_text(self) -> str:
        session_entry: SessionEntry | None = None
        messages: list[dict[str, Any]] = []
        if self.state.session_id:
            session_entry = next(
                (
                    entry
                    for entry in list_session_entries(self.project_root)
                    if entry.id == self.state.session_id
                ),
                None,
            )
            try:
                messages = DeepySession.open(
                    self.project_root,
                    self.state.session_id,
                ).get_items_sync()
            except Exception:
                messages = []
        return build_exit_summary_text(
            session=session_entry,
            messages=messages,
            model=self.settings.model.name,
            session_id=self.state.session_id,
            session_cost_unsupported=not supports_session_cost(self.settings),
        )

    def _capture_session_cost_start(self) -> dict[str, Any] | None:
        if not should_track_session_cost(self.settings):
            return None
        if self.state.session_id and self._session_cost_has_start(self.state.session_id):
            return None
        return balance_snapshot_to_dict(
            fetch_deepseek_balance(self.settings),
            captured_at_ms=_now_ms(),
        )

    def _record_pending_session_cost_start(self, session_id: str | None) -> None:
        if not session_id or self._pending_session_cost_start is None:
            return
        try:
            DeepySession.open(self.project_root, session_id).record_session_cost_start(
                self._pending_session_cost_start
            )
        except Exception:
            pass
        finally:
            self._pending_session_cost_start = None

    def _record_session_cost_end(self) -> None:
        session_id = self.state.session_id
        if (
            not session_id
            or not should_track_session_cost(self.settings)
            or not self._session_cost_has_start(session_id)
        ):
            return
        snapshot = balance_snapshot_to_dict(
            fetch_deepseek_balance(self.settings),
            captured_at_ms=_now_ms(),
        )
        try:
            DeepySession.open(self.project_root, session_id).record_session_cost_end(snapshot)
        except Exception:
            return

    def _session_cost_has_start(self, session_id: str) -> bool:
        return any(
            entry.id == session_id
            and isinstance(entry.session_cost, dict)
            and isinstance(entry.session_cost.get("start"), dict)
            for entry in list_session_entries(self.project_root)
        )

    def _clear_quit_confirm(self) -> None:
        if self.state.quit_confirm_pending:
            self.state = set_quit_confirm(self.state, False)
            self._update_status("Idle" if not self.state.busy else "Running")

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


async def _load_session_items(project_root: Path, session_id: str) -> list[dict[str, Any]]:
    try:
        return await DeepySession.open(project_root, session_id).get_items()
    except Exception:
        return []


def _session_title(items: list[dict[str, Any]]) -> str:
    for item in items:
        if _role(item) == "user":
            text = _visible_item_text(item)
            if text.strip():
                return text
    for item in items:
        text = _visible_item_text(item)
        if text.strip():
            return text
    return "Untitled"


def _session_status(items: list[dict[str, Any]]) -> str:
    if not items:
        return "empty"
    for item in reversed(items):
        if _role(item) == "user":
            break
        if _is_waiting_tool_output(item):
            return "waiting"
    last = items[-1]
    if _item_type(last) == "function_call":
        return "interrupted"
    if _is_failed_tool_output(last):
        return "failed"
    return "completed"


def _format_tui_session_label(preview: ResumeSessionPreview) -> str:
    title = format_session_title(preview.title, max_chars=36)
    return (
        f"{title}  {format_session_time(preview.updated_at)}"
        f" · {preview.status}"
        f" · {preview.active_tokens:,} tokens"
        f" · {preview.id[:8]}"
    )


def _is_waiting_tool_output(item: dict[str, Any]) -> bool:
    if _item_type(item) != "function_call_output" and _role(item) != "tool":
        return False
    return parse_tool_output(_tool_output_text(item)).await_user_response


def _is_failed_tool_output(item: dict[str, Any]) -> bool:
    if _item_type(item) != "function_call_output" and _role(item) != "tool":
        return False
    return parse_tool_output(_tool_output_text(item)).ok is False


def _is_local_command_tool_output(view: Any) -> bool:
    metadata = getattr(view, "metadata", None) or {}
    return getattr(view, "name", "") == "shell" and bool(metadata.get("localCommandMode"))


def _visible_item_text(item: dict[str, Any]) -> str:
    if "content" in item:
        return _item_text(item["content"])
    if "text" in item:
        return _item_text(item["text"])
    if "output" in item:
        return _item_text(item["output"])
    return ""


def _history_tool_call_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return DeepyStreamEvent(
        kind="tool_call",
        name=_tool_call_name(item),
        payload={
            "call_id": _call_id(item),
            "arguments": _tool_call_arguments(item),
        },
    )


def _raw_tool_call_event(event: DeepyStreamEvent) -> DeepyStreamEvent | None:
    if event.name != "response.output_item.added":
        return None
    raw = event.payload.get("raw")
    item = _raw_value(raw, "item")
    if item is None:
        return None
    item_type = _raw_str(item, "type")
    if item_type not in {"function_call", "custom_tool_call", "mcp_call"}:
        return None
    call_id = _raw_call_id(item)
    if not call_id:
        return None
    tool_name = _raw_tool_name(item)
    arguments = _raw_tool_arguments(item)
    return DeepyStreamEvent(
        kind="tool_call",
        name=tool_name,
        payload={"call_id": call_id, "arguments": arguments},
    )


def _history_tool_output_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return DeepyStreamEvent(
        kind="tool_output",
        payload={"call_id": _call_id(item)},
        text=_tool_output_text(item),
    )


def _item_text(content: Any) -> str:
    if isinstance(content, str):
        return redacted_content_text(content)
    if isinstance(content, list):
        return redacted_content_text(content)
    if content is None:
        return ""
    if isinstance(content, dict):
        image_text = redacted_content_text(content)
        if image_text:
            return image_text
        text = _content_part_text(content)
        return text or json_utils.dumps(content)
    return str(content)


def _reasoning_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("content", "summary", "text"):
        if key in item:
            text = _item_text(item[key])
            if text.strip():
                parts.append(text)
    return "\n".join(parts)


def _tool_output_text(item: dict[str, Any]) -> str:
    if "output" in item:
        return _item_text(item["output"])
    content = item.get("content")
    if isinstance(content, list):
        return json_utils.dumps(content)
    return _item_text(content)


def _content_part_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""
    for key in ("text", "input_text", "output_text", "refusal"):
        value = part.get(key)
        if isinstance(value, str):
            return value
    return ""


def _chat_tool_calls(item: dict[str, Any]) -> list[dict[str, Any]]:
    value = item.get("tool_calls")
    if not isinstance(value, list):
        return []
    return [tool_call for tool_call in value if isinstance(tool_call, dict)]


def _tool_call_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, str) and name:
        return name
    function = item.get("function")
    if isinstance(function, dict):
        function_name = function.get("name")
        if isinstance(function_name, str) and function_name:
            return function_name
    return "tool"


def _tool_call_arguments(item: dict[str, Any]) -> str:
    arguments = item.get("arguments")
    if isinstance(arguments, str):
        return arguments
    if arguments is not None:
        return json_utils.dumps(arguments)
    function = item.get("function")
    if isinstance(function, dict):
        function_arguments = function.get("arguments")
        if isinstance(function_arguments, str):
            return function_arguments
        if function_arguments is not None:
            return json_utils.dumps(function_arguments)
    return ""


def _raw_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _raw_str(item: Any, key: str) -> str:
    value = _raw_value(item, key)
    return value if isinstance(value, str) else ""


def _raw_call_id(item: Any) -> str:
    for key in ("call_id", "tool_call_id", "id"):
        value = _raw_str(item, key)
        if value:
            return value
    return ""


def _raw_tool_name(item: Any) -> str:
    for key in ("name", "tool_name"):
        value = _raw_str(item, key)
        if value:
            return value
    function = _raw_value(item, "function")
    value = _raw_str(function, "name")
    return value or "tool"


def _raw_tool_arguments(item: Any) -> str:
    arguments = _raw_value(item, "arguments")
    if isinstance(arguments, str):
        return arguments
    if arguments is not None:
        return json_utils.dumps(arguments)
    function = _raw_value(item, "function")
    function_arguments = _raw_value(function, "arguments")
    if isinstance(function_arguments, str):
        return function_arguments
    if function_arguments is not None:
        return json_utils.dumps(function_arguments)
    return ""


def _item_type(item: dict[str, Any]) -> str:
    value = item.get("type")
    return value if isinstance(value, str) else ""


def _recoverable_tool_key(name: str, argument_summary: str) -> tuple[str, str] | None:
    if name not in {"Write", "Update"}:
        return None
    target = _recoverable_tool_target(argument_summary)
    if not target:
        return None
    return name, target


def _recoverable_tool_target(argument_summary: str) -> str:
    text = " ".join(argument_summary.strip().split())
    if not text:
        return ""
    if ":" in text:
        text = text.rsplit(":", 1)[1].strip()
    if "," in text:
        text = text.split(",", 1)[0].strip()
    if " (" in text:
        text = text.split(" (", 1)[0].strip()
    for prefix in ("malformed args, ", "file: ", "files: "):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text


def _role(item: dict[str, Any]) -> str:
    value = item.get("role")
    return value if isinstance(value, str) else ""


def _call_id(item: dict[str, Any]) -> str:
    for key in ("call_id", "tool_call_id", "id"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


def _model_list_text() -> str:
    lines = ["Available providers and models:"]
    for provider in PROVIDER_CATALOG:
        lines.append(f"- {provider.id}: {provider.description}")
        for model in provider.models:
            lines.append(f"  - {model.name}: {model.description}")
        lines.append(f"  - thinking: {', '.join(provider.thinking_modes)}")
    return "\n".join(lines)


def _model_usage_text() -> str:
    return (
        "Usage: /model | /model list | "
        "/model set deepseek-v4-pro|deepseek-v4-flash [none|high|max] | "
        "/model set openrouter xiaomi/mimo-v2.5-pro none|minimal|low|medium|high|xhigh | "
        "/model set xiaomi mimo-v2.5-pro enabled|disabled | "
        "/model provider deepseek|openrouter|xiaomi | "
        "/model thinking <mode>"
    )


def _format_view_mode_confirmation(view_mode: str) -> str:
    reasoning_state = "reasoning shown" if view_mode == "full" else "reasoning hidden"
    return f"View: {view_mode} · {reasoning_state}"


def _is_light_tui_theme(shared_theme: str, textual_theme: str) -> bool:
    return shared_theme == "light" or textual_theme in _LIGHT_TEXTUAL_THEMES


def _reset_choice_description(description: str, *, default: bool = False) -> str:
    parts = [description] if description else []
    if default:
        parts.append("current default")
    return " · ".join(parts)


def _reset_config_validation_error(result: ResetConfigResult) -> str:
    if not result.provider:
        return "Provider is required."
    if not is_supported_provider(result.provider):
        return f"Invalid provider: {result.provider}\n{_model_usage_text()}"
    if not result.model:
        return "Model is required."
    if not (
        is_supported_model_for_provider(result.model, result.provider)
        or (allows_custom_model_for_provider(result.provider) and result.model.strip())
    ):
        return f"Invalid model: {result.model}\n{_model_usage_text()}"
    if result.thinking and not is_valid_thinking_mode_for_provider(result.thinking, result.provider):
        return f"Invalid thinking mode: {result.thinking}\n{_model_usage_text()}"
    if not result.base_url:
        return "Base URL is required."
    if not result.theme:
        return "Theme is required."
    if result.interface not in {"classic", "modern"}:
        return "Usage: UI must be classic|modern"
    if not is_valid_ui_theme(result.theme):
        return "Usage: theme must be dark|light"
    return ""


def _format_tui_ui_interface_label(interface: str) -> str:
    return "Modern UI" if interface == "modern" else "Classic UI"


def _build_tui_status_context(
    session_id: str | None,
    *,
    project_root: Path,
    settings: Settings,
    background_tasks: BackgroundTaskManager | None = None,
    audit_state: AuditModeState | None = None,
) -> str:
    segments = [
        f"provider {settings.model.provider}",
        f"model {settings.model.name}[{settings.model.reasoning_mode}]",
        f"cwd {format_home_relative_path(project_root)}",
        f"audit {_active_tui_audit_mode(audit_state, settings)}",
    ]
    if has_agents_instructions(project_root):
        segments.append("[AGENTS.md]")
    mcp_count = _configured_mcp_server_count(settings, project_root)
    if mcp_count > 0:
        segments.append(f"mcp {mcp_count}")
    if background_tasks is not None:
        running = background_tasks.running_count()
        if running:
            segments.append(f"bg {running}")
    session_entry = _tui_session_entry(project_root, session_id)
    segments.append(
        _format_tui_context_window_status(
            session_entry,
            settings.context.window_tokens,
            settings.context.resolved_compact_threshold,
        )
    )
    segments.append(_format_tui_status_cache_hit_rate(session_entry))
    return " · ".join(segments)


def _format_tui_status_cache_hit_rate(session_entry: Any | None) -> str:
    if session_entry is None:
        return "cache --"
    hit_rate = format_cache_hit_rate(getattr(session_entry, "cache_usage", None))
    if hit_rate == "unknown":
        return "cache --"
    return f"cache {hit_rate}"


def _format_tui_side_status(
    project_root: Path,
    settings: Settings,
    session_id: str | None,
    loaded_skill_names: list[str],
    todo_text: str,
    *,
    audit_state: AuditModeState | None = None,
) -> str:
    session_entry = _tui_session_entry(project_root, session_id)
    lines = [
        f"Project: {project_root}",
        f"Provider: {settings.model.provider}",
        f"Model: {settings.model.name}",
        f"Thinking: {settings.model.reasoning_mode}",
        f"Audit: {_format_tui_audit_mode(audit_state, settings)}",
        f"Session: {session_id or 'new'}",
        f"Cache: {_format_tui_cache_status(session_entry)}",
        f"Skills: {', '.join(loaded_skill_names) or 'none'}",
    ]
    if todo_text:
        lines.extend(["", "Todos:", todo_text])
    return "\n".join(lines)


def _active_tui_audit_mode(audit_state: AuditModeState | None, settings: Settings) -> str:
    if audit_state is not None:
        return audit_state.mode.value
    return settings.audit.mode.value


def _format_tui_audit_mode(audit_state: AuditModeState | None, settings: Settings) -> str:
    active = _active_tui_audit_mode(audit_state, settings)
    configured = settings.audit.mode.value
    if active == configured:
        return active
    return f"{active} (runtime, config {configured})"


def _format_tui_cache_status(session_entry: Any | None) -> str:
    if session_entry is None:
        return "unknown"
    parts: list[str] = []
    generation = getattr(session_entry, "cache_prefix_generation", 0)
    if generation:
        parts.append(f"gen {generation}")
    usage = format_cache_usage(getattr(session_entry, "cache_usage", None))
    if usage != "unknown":
        parts.append(usage)
    reason = getattr(session_entry, "cache_break_reason", None)
    if reason:
        parts.append(f"break {reason}")
    return " · ".join(parts) if parts else "unknown"


def _tui_session_entry(project_root: Path, session_id: str | None) -> Any | None:
    if not session_id:
        return None
    return next((entry for entry in list_session_entries(project_root) if entry.id == session_id), None)


def _configured_mcp_server_count(settings: Settings, project_root: Path) -> int:
    try:
        return len(load_mcp_config(settings, project_root=project_root).definitions)
    except Exception:
        return 0


def _format_tui_background_task_details(task: BackgroundTaskSnapshot) -> str:
    details: list[str] = []
    if task.pid is not None:
        details.append(f"pid `{task.pid}`")
    if task.exit_code is not None:
        details.append(f"exit `{task.exit_code}`")
    if task.stop_requested:
        details.append("stop requested")
    return ", ".join(details)


def _format_tui_background_tasks_transcript(tasks: Sequence[BackgroundTaskSnapshot]) -> str:
    if not tasks:
        return "Background Tasks\nNo background tasks."
    lines = ["Background Tasks"]
    for index, task in enumerate(tasks, start=1):
        lines.append(f"{index}. {task.id} {task.status}: {task.command}")
        details = _format_tui_background_task_details(task)
        if details:
            lines.append(f"   {details}")
    lines.append("")
    lines.append("Use /stop <id>, /stop <number>, or /stop all.")
    return "\n".join(lines)


def _parse_tui_background_stop_selection(
    running_tasks: Sequence[BackgroundTaskSnapshot],
    selection: str,
) -> str | None:
    normalized = selection.strip()
    if not normalized:
        return None
    if normalized.lower() in {"cancel", "c", "q", "quit"}:
        return None
    if normalized.lower() in {"all", "a", "*"}:
        return "all"
    if normalized.isdigit():
        index = int(normalized) - 1
        if index == len(running_tasks):
            return "all"
        if index == len(running_tasks) + 1:
            return None
        if 0 <= index < len(running_tasks):
            return running_tasks[index].id
        return "__invalid__"
    if any(task.id == normalized for task in running_tasks):
        return normalized
    return "__invalid__"


def _format_tui_context_window_status(
    session_entry: Any | None,
    window_tokens: int,
    compact_threshold: int,
) -> str:
    window_text = _format_token_count_short(window_tokens)
    if window_tokens <= 0:
        return "ctx unknown"
    if session_entry is not None and session_entry.latest_context_window_tokens is not None:
        used_tokens = session_entry.latest_context_window_tokens
    else:
        usage_payload = session_entry.usage if session_entry is not None else None
        usage = context_window_usage(usage_payload) if isinstance(usage_payload, dict) else None
        used_tokens = usage.used_tokens if usage is not None else None
    if used_tokens is None:
        return f"ctx unknown/{window_text}"
    percentage = used_tokens / window_tokens * 100
    status = f"ctx {_format_token_count_short(used_tokens)}/{window_text} ({percentage:.1f}%)"
    if compact_threshold > 0 and used_tokens >= compact_threshold:
        status = f"{status} · compact next"
    return status


def _format_token_count_short(value: int) -> str:
    if value < 1_000:
        return str(value)
    if value < 1_000_000:
        return f"{round(value / 1_000):g}K"
    scaled = value / 1_000_000
    if scaled >= 10:
        return f"{round(scaled):g}M"
    rounded = round(scaled, 1)
    return f"{rounded:g}M"


def _format_stream_token_count_short(value: int) -> str:
    if value >= 1_000:
        precision = 1 if value < 100_000 else 0
        formatted = f"{value / 1_000:.{precision}f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return f"{formatted}K"
    return str(value)


def _remove_local_skill_directory(path: Path) -> Path:
    skill_path = path / "SKILL.md"
    if not path.is_dir() or not skill_path.is_file():
        raise ValueError(f"Skill path is invalid: {path}")
    if path.parent.name != "skills" or path.parent.parent.name != ".agents":
        raise ValueError(f"Refusing to remove unexpected path: {path}")
    shutil.rmtree(path)
    return path


def _installed_skill_entries(project_root: Path) -> list[SkillScreenEntry]:
    records = {record.name.lower(): record for record in list_installed_skills()}
    entries: list[SkillScreenEntry] = []
    seen: set[str] = set()
    for skill in discover_skills(project_root):
        if skill.scope == "builtin":
            continue
        record = records.get(skill.name.lower())
        entries.append(
            SkillScreenEntry(
                name=skill.name,
                scope=record.scope if record is not None else skill.scope,
                description=skill.description,
                version=record.version if record is not None else "",
                path=str(record.install_path if record is not None else skill.path.parent),
                installed=True,
                managed_by_market=record is not None,
                source="installed",
                removable=skill.scope != "builtin",
            )
        )
        seen.add(skill.name.lower())
    for record in records.values():
        if record.name.lower() in seen:
            continue
        entries.append(
            SkillScreenEntry(
                name=record.name,
                scope=record.scope,
                version=record.version,
                path=str(record.install_path),
                installed=True,
                managed_by_market=True,
                source="installed",
                removable=True,
            )
        )
    return sorted(entries, key=lambda entry: (entry.scope != "project", entry.name))


def _market_skill_entry(skill: MarketSkill, *, local_names: set[str]) -> SkillScreenEntry:
    return SkillScreenEntry(
        name=skill.name,
        scope="market",
        description=skill.description,
        version=skill.version,
        installed=skill.installed or skill.name in local_names,
        managed_by_market=skill.installed,
        source="market",
    )


def _skill_detail_markdown(skill: SkillInfo) -> str:
    body = read_skill_body(skill) or "(empty skill)"
    return "\n\n".join(
        [
            f"# {skill.name}",
            f"- Scope: `{skill.scope}`",
            f"- Path: `{skill.path.parent}`",
            body,
        ]
    )


def _market_detail_markdown(entry: SkillScreenEntry) -> str:
    lines = [
        f"# {entry.name}",
        "",
        f"- Scope: `{entry.scope}`",
        f"- Version: `{entry.version or 'unknown'}`",
        f"- Installed: `{'yes' if entry.installed else 'no'}`",
    ]
    if entry.description:
        lines.extend(["", entry.description])
    return "\n".join(lines)


def _format_market_skills(skills: list[MarketSkill]) -> str:
    if not skills:
        return "No market skills found."
    lines = ["Market skills:"]
    for skill in skills:
        marker = " (installed)" if skill.installed else ""
        description = f" - {skill.description}" if skill.description else ""
        version = f" version={skill.version}" if skill.version else ""
        lines.append(f"- {skill.name}{marker}{version}{description}")
    return "\n".join(lines)


def _tool_output_diff_text(output: str) -> str | None:
    view = parse_tool_output(output)
    if view.ok is not True or view.name not in {"Write", "Update"}:
        return None
    return view.diff_preview or view.diff


def _widget_appears_before(left: Widget, right: Widget) -> bool:
    parent = left.parent
    if parent is None or parent is not right.parent:
        return False
    siblings = list(parent.children)
    try:
        return siblings.index(left) < siblings.index(right)
    except ValueError:
        return False


def _now_ms() -> int:
    return int(time.time() * 1000)


def _format_installed_records(records: list[InstalledSkill]) -> str:
    if not records:
        return "No market-installed skills."
    lines = ["Market-installed skills:"]
    for record in records:
        lines.append(
            f"- {record.name} ({record.scope}) -> {record.install_path} installed={record.installed_at}"
        )
    return "\n".join(lines)
