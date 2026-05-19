from __future__ import annotations

import asyncio
import shutil
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, Literal

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import var
from textual.widgets import Footer, Header, Label, Static

from deepy.config import (
    DEEPSEEK_MODEL_CATALOG,
    Settings,
    is_supported_deepseek_model,
    is_valid_reasoning_mode,
    is_valid_ui_theme,
    load_settings,
    update_config_input_suggestions_enabled,
    update_config_model_settings,
    update_config_theme,
    write_config,
)
from deepy.input_suggestions import (
    InputSuggestionController,
    generate_input_suggestion,
    is_eligible_for_input_suggestion,
)
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.mcp import load_mcp_config
from deepy.prompts.init_agents import build_agents_init_prompt
from deepy.prompts.rules import has_agents_instructions
from deepy.sessions import DeepyJsonlSession, SessionEntry, list_session_entries
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
    ResetConfigScreen,
    SkillManagementScreen,
    SkillScreenAction,
    SkillScreenEntry,
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
from deepy.ui.message_view import parse_tool_output
from deepy.ui.session_list import format_session_title
from deepy.ui.session_picker import ResumeSessionPreview, format_session_time
from deepy.ui.slash_commands import build_slash_commands
from deepy.ui.model_picker import REASONING_MODE_CHOICES
from deepy.ui.welcome import format_home_relative_path
from deepy.usage import context_window_usage, format_usage_line
from deepy.utils import json as json_utils


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
    COMMANDS = {DeepyCommandProvider}
    BINDINGS = [
        Binding("ctrl+d", "confirm_quit", "Quit", priority=True),
        Binding("escape", "interrupt_or_focus_prompt", "Interrupt"),
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

    #prompt-ghost {
        height: 1;
        margin: 0 1 0 1;
        color: $text-muted;
        text-style: italic;
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

    .block-body, .block-markdown, .tool-details, #side-status, #prompt-input {
        text-style: none;
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

    .tool-details {
        margin: 1 0 0 0;
        color: $text-muted;
        display: none;
    }

    .tool-block.-waiting {
        border-left: solid $warning;
    }

    .todo-block {
        border-left: solid $success;
    }

    .todo-block .block-title {
        color: $success;
    }

    .question-block {
        border-left: solid $warning;
        background: $boost;
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
        guide_missing_config: bool = False,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.project_root = project_root
        self.run_once = run_once
        self.guide_missing_config = guide_missing_config
        self.controller = TuiController(settings=settings)
        self.input_suggestions = InputSuggestionController(
            enabled=settings.ui.input_suggestions_enabled
        )
        self._assistant_block: AssistantBlock | None = None
        self._thinking_block: ThinkingBlock | None = None
        self._tool_blocks: dict[str, ToolBlock] = {}
        self._focused_block_index = -1
        self._pending_question_answers: OrderedDict[str, str] = OrderedDict()
        self._new_output_available = False
        self._todo_text = ""
        self._local_command_sequence = 0
        self.exit_summary_text: str | None = None

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
        self._scroll_transcript_to_end(force=True)
        self.query_one("#prompt-input", PromptTextArea).focus()
        self._update_status("Idle")
        if self.guide_missing_config and not self.settings.model.api_key:
            self.call_after_refresh(self._start_initial_setup)

    def _apply_theme(self) -> None:
        self.theme = "textual-light" if self.settings.ui.theme == "light" else "textual-dark"

    def _start_initial_setup(self) -> None:
        self.run_worker(self._initial_setup_command(), exclusive=False)

    async def _initial_setup_command(self) -> None:
        await self._append_block(InfoBlock("Deepy needs a DeepSeek API key before starting TUI."))
        await self._reset_command()

    @on(PromptTextArea.Submitted)
    async def on_prompt_submitted(self, event: PromptTextArea.Submitted) -> None:
        event.stop()
        self._clear_input_suggestion()
        if self.state.busy:
            self.notify("Deepy is still working.", severity="warning")
            return
        local_command = parse_local_command(event.text)
        if local_command is not None:
            await self._handle_local_command(local_command)
            return
        if await self._handle_prompt_command(event.text):
            return
        self.controller.add_prompt_history(event.text)
        await self._append_block(UserBlock(event.text))
        self._scroll_transcript_to_end(force=True)
        self._start_model_turn(event.text, list(self.controller.loaded_skill_names), status="Running")

    async def _handle_prompt_command(self, text: str) -> bool:
        slash = parse_slash_command(text)
        if slash is None:
            return False
        if slash.name in {"exit", "quit"}:
            self._exit_with_summary()
            return True
        if slash.name in UNSUPPORTED_TUI_COMMANDS:
            await self._append_block(ErrorBlock(UNSUPPORTED_TUI_COMMANDS[slash.name]))
            return True
        if slash.name == "init":
            request = build_agents_init_prompt(self.project_root, extra_instruction=slash.argument)
            await self._append_block(UserBlock(text))
            self._start_model_turn(request, list(self.controller.loaded_skill_names), status="Initializing AGENTS.md")
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
            "model",
            "input-suggestion",
            "reset",
        }:
            self.invoke_tui_command(slash.name, slash.argument)
            return True
        if slash.name == "skills":
            self.invoke_tui_command("skills", slash.argument)
            return True
        if slash.name.startswith("skill:"):
            skill_name = slash.name.removeprefix("skill:")
            skill = find_skill(self.project_root, skill_name)
            if skill is None:
                await self._append_block(ErrorBlock(f"Skill not found: {skill_name}"))
                return True
            request = slash.argument or f"Use the {skill.name} skill."
            await self._append_block(UserBlock(text))
            self._start_model_turn(request, [skill.name], status=f"Using skill {skill.name}")
            return True
        await self._append_block(ErrorBlock(f"Unsupported TUI command: /{slash.name}"))
        return True

    def _start_model_turn(self, prompt: str, skill_names: list[str], *, status: str) -> None:
        self._clear_input_suggestion()
        self.state = set_busy(reset_turn_buffers(self.state), True, status)
        self._assistant_block = None
        self._thinking_block = None
        self._tool_blocks.clear()
        self._update_status(status)
        self.run_model_turn(prompt, skill_names)

    def invoke_tui_command(self, name: str, argument: str = "") -> None:
        self.run_worker(self._run_tui_command(name, argument), exclusive=False)

    async def _run_tui_command(self, name: str, argument: str = "") -> None:
        if name == "help":
            self.push_screen(InfoScreen("Deepy TUI Help", self._help_markdown()))
            return
        if name == "status":
            self.push_screen(
                InfoScreen(
                    "Deepy TUI Status",
                    self._status_markdown(balance=fetch_deepseek_balance(self.settings)),
                )
            )
            return
        if name == "mcp":
            self.push_screen(InfoScreen("Deepy TUI MCP", self._mcp_markdown()))
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
        if name == "model":
            await self._model_command(argument.strip())
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
                "- **Shift+Enter** - insert newline\n"
                "- **Ctrl+P** - command palette\n"
                "- **Ctrl+O** - toggle side panel\n"
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
        lines = [
            "# Status",
            "",
            f"- Project: `{report.project_root}`",
            f"- Model: `{report.model}`",
            f"- Reasoning: `{report.reasoning_mode}`",
            f"- Session: `{self.state.session_id or 'new'}`",
            f"- Theme: `{self.settings.ui.theme}`",
            f"- Input suggestions: `{'enabled' if self.settings.ui.input_suggestions_enabled else 'disabled'}`",
            f"- Loaded skills: `{', '.join(self.controller.loaded_skill_names) or 'none'}`",
            f"- Sessions: `{report.session_count}`",
            f"- Skills: `{report.skill_count}`",
            f"- MCP: `{'enabled' if report.mcp.get('enabled') else 'disabled'}`",
            f"- Config: `{self.settings.path or 'unknown'}`",
            f"- Session usage: `{format_usage_line(report.active_session_usage) if report.active_session_usage else 'unknown'}`",
            f"- Project usage: `{format_usage_line(report.project_usage) if report.project_usage else 'unknown'}`",
        ]
        if balance is not None:
            lines.append(f"- Balance: `{format_balance_status(balance)}`")
        if include_runtime:
            lines.extend(["", "## Runtime", "```text", format_status_report(report), "```"])
        return "\n".join(lines)

    def _mcp_markdown(self) -> str:
        report = build_status_report(self.project_root, self.settings)
        lines = ["# MCP Status", ""]
        for key, value in report.mcp.items():
            lines.append(f"- {key}: `{value}`")
        return "\n".join(lines)

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
        return await self.push_screen_wait(ChoiceScreen(title, choices))

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
            theme = await self.push_screen_wait(
                ChoiceScreen(
                    "Select theme",
                    [
                        Choice("auto", "auto", "Follow saved/default theme behavior"),
                        Choice("dark", "dark", "Use Textual dark theme"),
                        Choice("light", "light", "Use Textual light theme"),
                    ],
                )
            ) or ""
        if not theme:
            self._update_status("Theme unchanged")
            return
        if not is_valid_ui_theme(theme):
            await self._append_block(ErrorBlock("Usage: /theme auto|dark|light"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist theme: config path is unknown."))
            return
        update_config_theme(self.settings.path, theme)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self.input_suggestions.set_enabled(self.settings.ui.input_suggestions_enabled)
        self._clear_input_suggestion()
        self._apply_theme()
        await self._append_block(InfoBlock(f"Saved UI theme: {theme}"))
        self._update_status(f"Theme {theme}")

    async def _model_command(self, argument: str) -> None:
        parts = argument.split()
        model: str | None = None
        reasoning: str | None = None
        if not parts:
            model = await self.push_screen_wait(
                ChoiceScreen(
                    "Select model",
                    [
                        Choice(item.name, item.name, item.description)
                        for item in DEEPSEEK_MODEL_CATALOG
                    ],
                )
            )
            if not model:
                self._update_status("Model unchanged")
                return
            reasoning = await self.push_screen_wait(
                ChoiceScreen(
                    "Select reasoning",
                    [Choice(value, value, label) for value, label in REASONING_MODE_CHOICES],
                )
            )
            if not reasoning:
                self._update_status("Model unchanged")
                return
        elif parts[0] == "list" and len(parts) == 1:
            await self._append_block(InfoBlock(_model_list_text()))
            return
        elif parts[0] == "set" and len(parts) in {2, 3}:
            model = parts[1]
            reasoning = parts[2] if len(parts) == 3 else None
        elif parts[0] in {"reasoning", "thinking"} and len(parts) == 2:
            reasoning = parts[1]
        else:
            await self._append_block(ErrorBlock(_model_usage_text()))
            return
        if model is not None and not is_supported_deepseek_model(model):
            await self._append_block(ErrorBlock(f"Invalid model: {model}\n{_model_usage_text()}"))
            return
        if reasoning is not None and not is_valid_reasoning_mode(reasoning):
            await self._append_block(ErrorBlock(f"Invalid reasoning mode: {reasoning}\n{_model_usage_text()}"))
            return
        if self.settings.path is None:
            await self._append_block(ErrorBlock("Cannot persist model settings: config path is unknown."))
            return
        update_config_model_settings(self.settings.path, model=model, reasoning_mode=reasoning)
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        await self._append_block(
            InfoBlock(
                f"Saved model: {self.settings.model.name} - reasoning: {self.settings.model.reasoning_mode}"
            )
        )
        self._update_status("Model saved")

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
        result = await self.push_screen_wait(
            ResetConfigScreen(
                api_key=self.settings.model.api_key or "",
                model=self.settings.model.name,
                base_url=self.settings.model.base_url,
                theme=self.settings.ui.theme,
            )
        )
        if result is None:
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
                model=result.model,
                base_url=result.base_url,
                theme=result.theme,
            )
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Config reset failed: {exc}"))
            return
        self.settings = load_settings(self.settings.path)
        self.controller.settings = self.settings
        self._apply_theme()
        await self._append_block(InfoBlock(f"Wrote {self.settings.path}"))
        self._update_status("Config reset")

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
                DeepyJsonlSession.open(self.project_root, self.state.session_id)
                if self.state.session_id
                else DeepyJsonlSession.create(self.project_root)
            )
            await session.add_items(build_synthetic_shell_transcript_items(command_input.raw_text, result))
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
        view = "market"
        while True:
            installed_entries = _installed_skill_entries(self.project_root)
            market_entries, market_error = await self._load_market_entries()
            action = await self.push_screen_wait(
                SkillManagementScreen(
                    installed_entries,
                    market_entries,
                    view=view,
                    market_error=market_error,
                )
            )
            if action is None:
                self._update_status("Skills closed")
                return
            view = action.source
            if action.action == "refresh":
                continue
            handled = await self._handle_skill_screen_action(action, market_entries)
            if not handled:
                return

    async def _handle_skill_screen_action(
        self,
        action: SkillScreenAction,
        market_entries: list[SkillScreenEntry],
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
                entry = next((item for item in market_entries if item.name == action.name), None)
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
            await self._skills_install(action.name)
            return True
        if action.action == "uninstall":
            await self._skills_uninstall(action.name)
            return True
        if action.action == "update":
            await self._skills_update(action.name)
            return True
        return False

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
        prompt = self.query_one("#prompt-input", PromptTextArea)
        previous = self.controller.previous_prompt(prompt.text)
        if previous is None:
            return
        prompt.text = previous
        prompt.move_cursor((0, len(prompt.text)))

    @on(PromptTextArea.HistoryNext)
    def on_history_next(self, event: PromptTextArea.HistoryNext) -> None:
        event.stop()
        prompt = self.query_one("#prompt-input", PromptTextArea)
        next_prompt = self.controller.next_prompt()
        if next_prompt is None:
            return
        prompt.text = next_prompt
        prompt.move_cursor((0, len(prompt.text)))

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
            await self._show_pending_question(summary.pending_questions)
        await self._append_block(UsageLine(format_usage_line(summary.usage)))
        self._update_status("Idle")
        self.run_worker(self._prepare_input_suggestion(summary), exclusive=False)

    @on(TurnFailedMessage)
    async def on_turn_failed(self, message: TurnFailedMessage) -> None:
        message.stop()
        self.state = set_busy(self.state, False, "Error")
        await self._append_block(ErrorBlock(str(message.error)))
        self._update_status("Error")

    @on(QuestionBlock.Answered)
    async def on_question_answered(self, message: QuestionBlock.Answered) -> None:
        message.stop()
        self._pending_question_answers[message.question] = message.answer
        await self._append_block(UserBlock(f"{message.question}\n{message.answer}"))
        questions = normalize_questions(self.state.pending_questions)
        if len(self._pending_question_answers) < len(questions):
            await self._append_block(QuestionBlock(questions[len(self._pending_question_answers)]))
            return
        continuation = format_ask_user_question_answers(self._pending_question_answers)
        self._pending_question_answers.clear()
        self.state = set_pending_questions(self.state, [])
        self.state = set_busy(reset_turn_buffers(self.state), True, "Running")
        self._assistant_block = None
        self._thinking_block = None
        self._tool_blocks.clear()
        self._update_status("Running")
        self.run_model_turn(continuation, list(self.controller.loaded_skill_names))

    @on(QuestionBlock.Cancelled)
    async def on_question_cancelled(self, message: QuestionBlock.Cancelled) -> None:
        message.stop()
        self._pending_question_answers.clear()
        self.state = set_pending_questions(self.state, [])
        await self._append_block(UserBlock(format_ask_user_question_decline()))
        self._update_status("Question cancelled")

    async def _show_pending_question(self, pending_questions: list[dict[str, Any]]) -> None:
        questions = normalize_questions(pending_questions)
        if not questions:
            await self._append_block(UserBlock(f"Questions pending: {len(pending_questions)}"))
            return
        self._pending_question_answers.clear()
        await self._append_block(QuestionBlock(questions[0]))

    async def _prepare_input_suggestion(self, summary: RunSummary) -> None:
        self._clear_input_suggestion()
        if not summary.session_id or summary.pending_questions:
            return
        session = DeepyJsonlSession.open(self.project_root, summary.session_id)
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

    async def _handle_stream_event(self, event: DeepyStreamEvent) -> None:
        if event.kind == "text_delta" and event.text:
            self.state = add_assistant_delta(self.state, event.text)
            if self._assistant_block is not None:
                anchored = self._transcript_is_anchored_now()
                self._assistant_block.update_markdown(self.state.assistant_buffer)
                self._scroll_transcript_to_end(force=anchored)
            return
        if event.kind == "message" and event.text:
            if not self.state.assistant_buffer:
                self.state = add_assistant_delta(self.state, event.text)
                if self._assistant_block is not None:
                    anchored = self._transcript_is_anchored_now()
                    self._assistant_block.update_markdown(self.state.assistant_buffer)
                    self._scroll_transcript_to_end(force=anchored)
            return
        if event.kind == "reasoning_delta" and event.text:
            self.state = add_reasoning_delta(self.state, event.text)
            if self._thinking_block is None:
                self._thinking_block = ThinkingBlock(event.text)
                await self._append_block(self._thinking_block)
            else:
                anchored = self._transcript_is_anchored_now()
                self._thinking_block.update_text(self._thinking_block.body + event.text)
                self._scroll_transcript_to_end(force=anchored)
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
                anchored = self._transcript_is_anchored_now()
                block.update_from_output(view)
                self._scroll_transcript_to_end(force=anchored)
            if view.name == "todo_write":
                self._todo_text = block.body
                self._update_status(self.state.status)
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
        anchored = self._transcript_is_anchored(transcript)
        await transcript.mount(block)
        self._scroll_transcript_to_end(force=anchored)

    async def _clear_transcript(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        await transcript.remove_children()
        self._assistant_block = None
        self._thinking_block = None
        self._tool_blocks.clear()
        self._focused_block_index = -1

    async def _restore_transcript(self, session_id: str) -> None:
        await self._clear_transcript()
        session = DeepyJsonlSession.open(self.project_root, session_id)
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
            if text.strip():
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
        if self._assistant_block is None:
            self._assistant_block = AssistantBlock(self.state.assistant_buffer)
            await self._append_block(self._assistant_block)
            return
        self._assistant_block.update_markdown(self.state.assistant_buffer)
        self._scroll_transcript_to_end(force=self._transcript_is_anchored_now())

    def _scroll_transcript_to_end(self, *, force: bool = False) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        if not force and not self._transcript_is_anchored(transcript):
            self._new_output_available = True
            self._set_status_bar("New output below")
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
        self.query_one("#side-status", Static).update(
            f"Project: {self.project_root}\n"
            f"Model: {self.settings.model.name}\n"
            f"Reasoning: {self.settings.model.reasoning_mode}\n"
            f"Session: {self.state.session_id or 'new'}\n"
            f"Skills: {', '.join(self.controller.loaded_skill_names) or 'none'}"
            + (f"\n\nTodos:\n{self._todo_text}" if self._todo_text else "")
        )

    def _set_status_bar(self, status: str) -> None:
        display = (
            f"{status} · New output below"
            if self._new_output_available and status != "New output below"
            else status
        )
        try:
            status_bar = self.query_one(StatusBar)
        except NoMatches:
            return
        status_bar.update_status(display, self._status_context())

    def _status_context(self) -> str:
        return _build_tui_status_context(
            self.state.session_id,
            project_root=self.project_root,
            settings=self.settings,
        )

    def action_confirm_quit(self) -> None:
        if self.state.quit_confirm_pending:
            self._exit_with_summary()
            return
        self.state = set_quit_confirm(self.state, True)
        self._update_status("Press Ctrl+D again to exit")
        self.set_timer(2.0, self._clear_quit_confirm)

    def _exit_with_summary(self) -> None:
        self.exit_summary_text = self._build_exit_summary_text()
        self.exit()

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
                messages = DeepyJsonlSession.open(
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
        )

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


async def _load_session_items(project_root: Path, session_id: str) -> list[dict[str, Any]]:
    try:
        return await DeepyJsonlSession.open(project_root, session_id).get_items()
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


def _history_tool_output_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return DeepyStreamEvent(
        kind="tool_output",
        payload={"call_id": _call_id(item)},
        text=_tool_output_text(item),
    )


def _item_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            text = _content_part_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if content is None:
        return ""
    if isinstance(content, dict):
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


def _item_type(item: dict[str, Any]) -> str:
    value = item.get("type")
    return value if isinstance(value, str) else ""


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
    lines = ["Available models:"]
    for model in DEEPSEEK_MODEL_CATALOG:
        lines.append(f"- {model.name}: {model.description}")
    lines.append("Reasoning modes:")
    for value, label in REASONING_MODE_CHOICES:
        lines.append(f"- {value}: {label}")
    return "\n".join(lines)


def _model_usage_text() -> str:
    return (
        "Usage: /model | /model list | "
        "/model set deepseek-v4-pro|deepseek-v4-flash [none|high|max] | "
        "/model reasoning none|high|max"
    )


def _reset_config_validation_error(result: ResetConfigResult) -> str:
    if not result.model:
        return "Model is required."
    if not is_supported_deepseek_model(result.model):
        return f"Invalid model: {result.model}\n{_model_usage_text()}"
    if not result.base_url:
        return "Base URL is required."
    if not result.theme:
        return "Theme is required."
    if not is_valid_ui_theme(result.theme):
        return "Usage: theme must be auto|dark|light"
    return ""


def _build_tui_status_context(
    session_id: str | None,
    *,
    project_root: Path,
    settings: Settings,
) -> str:
    segments = [
        f"model {settings.model.name}[{settings.model.reasoning_mode}]",
        f"cwd {format_home_relative_path(project_root)}",
    ]
    if has_agents_instructions(project_root):
        segments.append("[AGENTS.md]")
    mcp_count = _configured_mcp_server_count(settings, project_root)
    if mcp_count > 0:
        segments.append(f"mcp {mcp_count}")
    segments.append(
        _format_tui_context_window_status(
            _tui_session_entry(project_root, session_id),
            settings.context.window_tokens,
            settings.context.resolved_compact_threshold,
        )
    )
    return " · ".join(segments)


def _tui_session_entry(project_root: Path, session_id: str | None) -> Any | None:
    if not session_id:
        return None
    return next((entry for entry in list_session_entries(project_root) if entry.id == session_id), None)


def _configured_mcp_server_count(settings: Settings, project_root: Path) -> int:
    try:
        return len(load_mcp_config(settings, project_root=project_root).definitions)
    except Exception:
        return 0


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
    remaining_tokens = max(window_tokens - used_tokens, 0)
    percentage = used_tokens / window_tokens * 100
    status = (
        f"ctx {_format_token_count_short(used_tokens)}/{window_text} "
        f"({percentage:.1f}%, {_format_token_count_short(remaining_tokens)} left)"
    )
    if compact_threshold > 0 and used_tokens >= compact_threshold:
        status = f"{status} · compact next"
    return status


def _format_token_count_short(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
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


def _format_installed_records(records: list[InstalledSkill]) -> str:
    if not records:
        return "No market-installed skills."
    lines = ["Market-installed skills:"]
    for record in records:
        lines.append(
            f"- {record.name} ({record.scope}) -> {record.install_path} installed={record.installed_at}"
        )
    return "\n".join(lines)
