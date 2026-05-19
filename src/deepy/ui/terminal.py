from __future__ import annotations

import asyncio
import contextlib
import os
import re
import select
import shutil
import threading
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Prompt
from rich.text import Text

from deepy import __version__
from deepy.config import (
    DEEPSEEK_MODEL_CATALOG,
    Settings,
    UI_THEMES,
    is_supported_deepseek_model,
    is_valid_reasoning_mode,
    load_settings,
    ui_theme_from_selection,
    ui_theme_number,
    update_config_input_suggestions_enabled,
    update_config_model_settings,
    update_config_theme,
    write_config,
)
from deepy.input_suggestions import (
    InputSuggestion,
    InputSuggestionController,
    generate_input_suggestion,
    is_eligible_for_input_suggestion,
)
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.compaction import ContextCompactionError
from deepy.llm.runner import RunSummary, run_prompt_once
from deepy.mcp import DeepyMcpRuntime, format_mcp_status
from deepy.prompts.init_agents import build_agents_init_prompt
from deepy.prompts.rules import has_agents_instructions
from deepy.sessions import DeepyJsonlSession, SessionEntry, list_session_entries
from deepy.sessions.manager import DeepySessionManager
from deepy.skill_market import (
    install_market_skill,
    list_installed_skills,
    search_market_skills,
    uninstall_market_skill,
    update_market_skill,
)
from deepy.skills import SkillInfo, discover_skills, find_skill, format_skills_for_terminal, read_skill_body
from deepy.status import build_status_report, format_status_report
from deepy.update_check import VersionUpdate
from deepy.update_check import check_for_version_update
from deepy.ui.ask_user_question import OTHER_VALUE
from deepy.ui.ask_user_question import AskUserQuestionItem
from deepy.ui.ask_user_question import AskUserQuestionOptionEntry
from deepy.ui.ask_user_question import build_answer_for_question
from deepy.ui.ask_user_question import build_options
from deepy.ui.ask_user_question import format_ask_user_question_answers
from deepy.ui.ask_user_question import format_ask_user_question_decline
from deepy.ui.ask_user_question import normalize_questions
from deepy.ui.exit_summary import build_exit_summary_text
from deepy.ui.local_command import (
    LocalCommandInput,
    build_synthetic_shell_transcript_items,
    parse_local_command,
    run_local_command,
    shell_tool_result_json,
)
from deepy.ui.message_view import (
    format_tool_display_label,
    format_tool_call_summary,
    format_tool_progress_summary,
    parse_tool_output,
    render_shell_output_block,
    render_todo_board,
    render_tool_diff_preview,
)
from deepy.ui.markdown import render_markdown
from deepy.ui.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.prompt_input import build_prompt_toolbar, create_prompt_session, measure_text_rows, prompt_for_input
from deepy.ui.session_list import resolve_session_selection
from deepy.ui.session_picker import ResumeSessionPreview
from deepy.ui.session_picker import format_resume_session_choices
from deepy.ui.session_picker import pick_resume_session
from deepy.ui.skill_picker import (
    InstalledSkillView,
    SkillDetailView,
    SkillMenuAction,
    pick_skill_install_scope,
    pick_skill_menu_action,
    show_skill_detail_view,
)
from deepy.ui.slash_commands import build_slash_commands
from deepy.ui.status_footer import StatusFooter, StatusFooterSegment
from deepy.ui.styles import (
    DARK_PALETTE,
    UiPalette,
    resolve_ui_palette,
    status_style,
)
from deepy.ui.theme_picker import THEME_CHOICES, pick_theme
from deepy.ui.model_picker import REASONING_MODE_CHOICES, pick_model, pick_reasoning_mode
from deepy.ui.welcome import build_welcome_panel
from deepy.ui.welcome import format_home_relative_path
from deepy.usage import TokenUsage, context_window_usage, format_usage_line
from deepy.utils import json as json_utils


try:
    import termios as _termios
    import tty as _tty
except ImportError:  # pragma: no cover - exercised on Windows.
    termios: Any | None = None
    tty: Any | None = None
else:
    termios = _termios
    tty = _tty

msvcrt: Any | None
try:
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised on non-Windows platforms.
    msvcrt = None
else:
    msvcrt = _msvcrt


RunOnce = Callable[..., Coroutine[Any, Any, RunSummary]]
InputFunc = Callable[[str], str]
VersionUpdateChecker = Callable[[str], VersionUpdate | None]
MAX_CLARIFICATION_ROUNDS_PER_TURN = 5


@dataclass(frozen=True)
class SlashCommand:
    name: str
    argument: str = ""


@dataclass(frozen=True)
class ToolCallDisplay:
    summary: str
    name: str


def parse_slash_command(text: str) -> SlashCommand | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    command, _, argument = stripped[1:].partition(" ")
    return SlashCommand(name=command, argument=argument.strip())


def run_interactive(
    settings: Settings,
    *,
    project_root: Path | None = None,
    console: Console | None = None,
    run_once: RunOnce = run_prompt_once,
    version_update_checker: VersionUpdateChecker | None = check_for_version_update,
) -> int:
    root = (project_root or Path.cwd()).resolve()
    output = console or Console()
    session_id: str | None = None
    version_update = _check_startup_version_update(version_update_checker)
    settings = _ensure_interactive_theme(settings)
    palette = resolve_ui_palette(settings.ui.theme)

    loaded_skill_names: list[str] = []
    ctrl_d_exit_pending = False
    context_footer = _build_status_footer(
        session_id,
        project_root=root,
        settings=settings,
    )
    input_suggestions = InputSuggestionController(
        enabled=settings.ui.input_suggestions_enabled
    )
    prompt_session = _create_interactive_prompt_session(
        root,
        palette,
        loaded_skill_names,
        input_suggestions=input_suggestions,
    )
    async_runner = asyncio.Runner()
    mcp_runtime = DeepyMcpRuntime(settings, project_root=root)
    async_runner.run(mcp_runtime.connect())
    context_footer = _build_status_footer(
        session_id,
        project_root=root,
        settings=settings,
        mcp_runtime=mcp_runtime,
    )
    output.print(
        build_welcome_panel(
            model=settings.model.name,
            thinking_enabled=settings.model.thinking_enabled,
            reasoning_effort=settings.model.reasoning_effort,
            project_root=root,
            skills=discover_skills(root),
            current_version=__version__,
            version_update=version_update,
            theme=settings.ui.theme,
            resolved_theme=palette.name,
            palette=palette,
        )
    )

    try:
        while True:
            try:
                text = prompt_for_input(
                    prompt_session,
                    bottom_toolbar=build_prompt_toolbar(context_footer),
                    input_suggestions=input_suggestions,
                )
                input_suggestions.dismiss()
            except EOFError:
                if ctrl_d_exit_pending:
                    output.print()
                    return 0
                ctrl_d_exit_pending = True
                output.print(f"[{palette.muted}]Press Ctrl+D again to exit.[/]")
                continue
            except KeyboardInterrupt:
                output.print()
                return 0

            if text == CTRL_D_EXIT_CONFIRM_SIGNAL:
                if ctrl_d_exit_pending:
                    output.print()
                    return 0
                ctrl_d_exit_pending = True
                output.print(f"[{palette.muted}]Press Ctrl+D again to exit.[/]")
                continue

            ctrl_d_exit_pending = False
            if not text:
                continue

            local_command = parse_local_command(text)
            if local_command is not None:
                session_id = _handle_local_command(
                    local_command,
                    output,
                    root,
                    session_id,
                    settings=settings,
                    palette=palette,
                    mcp_runtime=mcp_runtime,
                )
                context_footer = _build_status_footer(
                    session_id,
                    project_root=root,
                    settings=settings,
                    mcp_runtime=mcp_runtime,
                )
                continue

            slash = parse_slash_command(text)
            if slash is not None:
                if slash.name.startswith("skill:"):
                    skill_name = slash.name.removeprefix("skill:")
                    skill = find_skill(root, skill_name)
                    if skill is None:
                        output.print(f"[{palette.error}]Skill not found:[/] {skill_name}")
                        continue
                    request = slash.argument or f"Use the {skill.name} skill."
                    anchor_status_output = _print_submitted_user_input(output, text, palette=palette)
                    summary = _run_once_with_status(
                        output,
                        run_once,
                        request,
                        project_root=root,
                        settings=settings,
                        session_id=session_id,
                        skill_names=[skill.name],
                        palette=palette,
                        async_runner=async_runner,
                        mcp_runtime=mcp_runtime,
                        anchor_status_output_lines=1 if anchor_status_output else 0,
                    )
                    session_id = summary.session_id
                    clarification_rounds = 0
                    while summary.status == "waiting_for_user":
                        if clarification_rounds >= MAX_CLARIFICATION_ROUNDS_PER_TURN:
                            output.print(
                                f"[{palette.muted}]Stopped after {MAX_CLARIFICATION_ROUNDS_PER_TURN} "
                                "clarification rounds. Please continue with a narrower request.[/]"
                            )
                            break
                        response = _collect_pending_question_response(output, summary.pending_questions)
                        if not response:
                            break
                        clarification_rounds += 1
                        summary = _run_once_with_status(
                            output,
                            run_once,
                            response,
                            project_root=root,
                            settings=settings,
                            session_id=session_id,
                            skill_names=[skill.name],
                            palette=palette,
                            async_runner=async_runner,
                            mcp_runtime=mcp_runtime,
                            anchor_status_output=True,
                        )
                        session_id = summary.session_id
                    _print_assistant_output(output, summary.output, palette=palette)
                    _print_usage_footer(output, summary, settings=settings, project_root=root, palette=palette)
                    _prepare_input_suggestion(
                        async_runner,
                        input_suggestions,
                        root,
                        settings,
                        summary,
                    )
                    context_footer = _build_status_footer(
                        summary.session_id,
                        project_root=root,
                        settings=settings,
                        mcp_runtime=mcp_runtime,
                    )
                    continue
                if slash.name == "init":
                    anchor_status_output = _print_submitted_user_input(output, text, palette=palette)
                    summary = _run_once_with_status(
                        output,
                        run_once,
                        build_agents_init_prompt(root, extra_instruction=slash.argument),
                        project_root=root,
                        settings=settings,
                        session_id=session_id,
                        skill_names=list(loaded_skill_names),
                        palette=palette,
                        async_runner=async_runner,
                        mcp_runtime=mcp_runtime,
                        anchor_status_output_lines=1 if anchor_status_output else 0,
                    )
                    session_id = summary.session_id
                    _print_assistant_output(output, summary.output, palette=palette)
                    _print_usage_footer(output, summary, settings=settings, project_root=root, palette=palette)
                    _prepare_input_suggestion(
                        async_runner,
                        input_suggestions,
                        root,
                        settings,
                        summary,
                    )
                    context_footer = _build_status_footer(
                        summary.session_id,
                        project_root=root,
                        settings=settings,
                        mcp_runtime=mcp_runtime,
                    )
                    continue
                next_session = _handle_slash_command(
                    slash,
                    output,
                    root,
                    session_id,
                    loaded_skill_names,
                    settings=settings,
                    palette=palette,
                    mcp_runtime=mcp_runtime,
                )
                if next_session == "__exit__":
                    return 0
                if slash.name in {"theme", "reset", "model"}:
                    settings = load_theme_settings(settings)
                    input_suggestions.set_enabled(settings.ui.input_suggestions_enabled)
                    palette = resolve_ui_palette(settings.ui.theme)
                if slash.name == "input-suggestion":
                    settings = load_settings(settings.path) if settings.path is not None else settings
                    input_suggestions.set_enabled(settings.ui.input_suggestions_enabled)
                if slash.name in {"skills", "theme", "reset", "model", "input-suggestion"}:
                    prompt_session = _create_interactive_prompt_session(
                        root,
                        palette,
                        loaded_skill_names,
                        input_suggestions=input_suggestions,
                    )
                session_id = next_session
                if slash.name in {"new", "resume", "reset", "model", "compact", "skills", "theme", "mcp"}:
                    context_footer = _build_status_footer(
                        session_id,
                        project_root=root,
                        settings=settings,
                        mcp_runtime=mcp_runtime,
                    )
                continue

            anchor_status_output = _print_submitted_user_input(output, text, palette=palette)
            summary = _run_once_with_status(
                output,
                run_once,
                text,
                project_root=root,
                settings=settings,
                session_id=session_id,
                skill_names=list(loaded_skill_names),
                palette=palette,
                async_runner=async_runner,
                mcp_runtime=mcp_runtime,
                anchor_status_output_lines=1 if anchor_status_output else 0,
            )
            session_id = summary.session_id
            clarification_rounds = 0
            while summary.status == "waiting_for_user":
                if clarification_rounds >= MAX_CLARIFICATION_ROUNDS_PER_TURN:
                    output.print(
                        f"[{palette.muted}]Stopped after {MAX_CLARIFICATION_ROUNDS_PER_TURN} "
                        "clarification rounds. Please continue with a narrower request.[/]"
                    )
                    break
                response = _collect_pending_question_response(output, summary.pending_questions)
                if not response:
                    break
                clarification_rounds += 1
                summary = _run_once_with_status(
                    output,
                    run_once,
                    response,
                    project_root=root,
                    settings=settings,
                    session_id=session_id,
                    skill_names=list(loaded_skill_names),
                    palette=palette,
                    async_runner=async_runner,
                    mcp_runtime=mcp_runtime,
                    anchor_status_output=True,
                )
                session_id = summary.session_id
            _print_assistant_output(output, summary.output, palette=palette)
            _print_usage_footer(output, summary, settings=settings, project_root=root, palette=palette)
            _prepare_input_suggestion(
                async_runner,
                input_suggestions,
                root,
                settings,
                summary,
            )
            context_footer = _build_status_footer(
                summary.session_id,
                project_root=root,
                settings=settings,
                mcp_runtime=mcp_runtime,
            )
    finally:
        async_runner.run(mcp_runtime.cleanup())
        async_runner.close()

def _create_interactive_prompt_session(
    root: Path,
    palette: UiPalette,
    loaded_skill_names: list[str],
    input_suggestions: InputSuggestionController | None = None,
):
    return create_prompt_session(
        slash_commands=build_slash_commands(
            discover_skills(root),
            loaded_skill_names=loaded_skill_names,
        ),
        palette=palette,
        project_root=root,
        input_suggestions=input_suggestions,
    )


def _prepare_input_suggestion(
    async_runner: asyncio.Runner,
    controller: InputSuggestionController,
    project_root: Path,
    settings: Settings,
    summary: RunSummary,
) -> None:
    controller.dismiss()
    if not summary.session_id or summary.pending_questions:
        return
    try:
        suggestion = async_runner.run(
            _generate_input_suggestion_for_summary(project_root, settings, summary)
        )
    except Exception:
        return
    if suggestion is None:
        return
    controller.set_suggestion(suggestion.text)
    session = DeepyJsonlSession.open(project_root, summary.session_id)
    session.record_input_suggestion_usage(
        suggestion.usage,
        model=suggestion.model,
        elapsed_ms=suggestion.elapsed_ms,
    )


async def _generate_input_suggestion_for_summary(
    project_root: Path,
    settings: Settings,
    summary: RunSummary,
) -> InputSuggestion | None:
    session = DeepyJsonlSession.open(project_root, summary.session_id)
    items = await session.get_items()
    if not is_eligible_for_input_suggestion(
        items,
        enabled=settings.ui.input_suggestions_enabled,
        has_pending_questions=bool(summary.pending_questions),
        turn_status=summary.status,
    ):
        return None
    return await generate_input_suggestion(settings, items)


def _check_startup_version_update(
    version_update_checker: VersionUpdateChecker | None,
) -> VersionUpdate | None:
    if version_update_checker is None:
        return None
    try:
        return version_update_checker(__version__)
    except Exception:
        return None


def _ensure_interactive_theme(settings: Settings) -> Settings:
    if settings.path is None or settings.ui.theme_configured:
        return settings
    theme = _prompt_theme_choice(settings.ui.theme)
    update_config_theme(settings.path, theme)
    return load_settings(settings.path)


def _prompt_theme_choice(default: str = "auto") -> str:
    _print_theme_choices(Console())
    value = Prompt.ask("UI theme number", default=ui_theme_number(default))
    return ui_theme_from_selection(value, default=default)


def load_theme_settings(settings: Settings) -> Settings:
    if settings.path is None:
        return settings
    try:
        return load_settings(settings.path)
    except Exception:
        return settings


def _run_once_with_status(
    console: Console,
    run_once: RunOnce,
    prompt: str,
    **kwargs: Any,
) -> RunSummary:
    async_runner = kwargs.pop("async_runner", None)
    palette = kwargs.pop("palette", DARK_PALETTE)
    original_emit_event = kwargs.pop("emit_event", None)
    original_should_interrupt = kwargs.pop("should_interrupt", None)
    anchor_status_output = bool(kwargs.pop("anchor_status_output", False))
    anchor_status_output_lines = int(kwargs.pop("anchor_status_output_lines", 0))
    project_root = kwargs.get("project_root")
    project_root_text = str(project_root) if project_root is not None else None
    settings = kwargs.get("settings")
    footer = _build_status_footer(
        kwargs.get("session_id"),
        project_root=project_root if isinstance(project_root, Path) else None,
        settings=settings if isinstance(settings, Settings) else None,
        mcp_runtime=kwargs.get("mcp_runtime"),
    )
    renderer: TerminalStreamRenderer | None = None
    started_at = time.monotonic()
    interrupt_requested = threading.Event()

    def should_interrupt() -> bool:
        if interrupt_requested.is_set():
            return True
        if callable(original_should_interrupt):
            return bool(original_should_interrupt())
        return False

    kwargs["should_interrupt"] = should_interrupt

    active_palette = palette if isinstance(palette, UiPalette) else DARK_PALETTE
    with _status_display(
        console,
        _working_status_text(started_at, palette=active_palette, footer=footer),
        palette=active_palette,
        anchor_output=anchor_status_output,
        anchor_output_lines=anchor_status_output_lines,
    ) as status:
        renderer = TerminalStreamRenderer(
            console,
            project_root=project_root_text,
            status=status,
            status_started_at=started_at,
            palette=active_palette,
            footer=footer,
        )
        stop_status_refresh = threading.Event()
        status_thread = threading.Thread(
            target=_refresh_working_status,
            args=(renderer, stop_status_refresh),
            daemon=True,
        )
        status_thread.start()

        try:
            with _esc_interrupt_watcher(interrupt_requested):
                def emit_event(event: DeepyStreamEvent) -> None:
                    renderer(event)
                    if callable(original_emit_event):
                        original_emit_event(event)

                coroutine = run_once(prompt, **kwargs, emit_event=emit_event)
                if isinstance(async_runner, asyncio.Runner):
                    summary = async_runner.run(coroutine)
                else:
                    summary = asyncio.run(coroutine)
        finally:
            stop_status_refresh.set()
            status_thread.join(timeout=0.2)

    renderer.flush()
    return summary


def _handle_local_command(
    command_input: LocalCommandInput,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    *,
    settings: Settings,
    palette: UiPalette | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
) -> str | None:
    palette = palette or resolve_ui_palette(settings.ui.theme)
    if not command_input.command:
        console.print(f"[{palette.error}]Usage:[/] !<command>")
        return current_session_id

    anchor_status_output = _print_submitted_user_input(console, command_input.raw_text, palette=palette)
    started_at = time.monotonic()
    interrupt_requested = threading.Event()
    with _status_display(
        console,
        _local_command_status_text(
            command_input.command,
            started_at,
            palette=palette,
            footer=_build_status_footer(
                current_session_id,
                project_root=project_root,
                settings=settings,
                mcp_runtime=mcp_runtime,
                active_work="running local command",
            ),
        ),
        palette=palette,
        anchor_output_lines=1 if anchor_status_output else 0,
    ):
        with _esc_interrupt_watcher(interrupt_requested):
            result = run_local_command(
                command_input.command,
                cwd=project_root,
                should_interrupt=interrupt_requested.is_set,
            )

    tool_output = shell_tool_result_json(result, output=result.display_output)
    call_summary = format_tool_call_summary(
        "shell",
        json_utils.dumps({"command": result.command}),
        project_root=str(project_root),
    )
    console.print(
        _status_line(
            format_tool_progress_summary(call_summary, tool_output),
            status_style(result.ok, palette),
        )
    )
    shell_output = render_shell_output_block(tool_output, palette=palette)
    if shell_output:
        console.print(shell_output)

    session = (
        DeepyJsonlSession.open(project_root, current_session_id)
        if current_session_id
        else DeepyJsonlSession.create(project_root)
    )
    try:
        asyncio.run(
            session.add_items(
                build_synthetic_shell_transcript_items(command_input.raw_text, result)
            )
        )
    except Exception as exc:
        console.print(f"[{palette.error}]Failed to persist local command transcript:[/] {exc}")
        return current_session_id
    return session.session_id


@contextlib.contextmanager
def _esc_interrupt_watcher(interrupt_requested: threading.Event):
    if termios is not None and tty is not None and Path("/dev/tty").exists():
        target = _watch_posix_esc_keypress
    elif msvcrt is not None:
        target = _watch_windows_esc_keypress
    else:
        yield
        return

    stop_event = threading.Event()
    thread = threading.Thread(
        target=target,
        args=(interrupt_requested, stop_event),
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=0.2)


def _watch_posix_esc_keypress(
    interrupt_requested: threading.Event,
    stop_event: threading.Event,
) -> None:
    fd: int | None = None
    old_attrs: list[Any] | None = None
    try:
        if termios is None or tty is None:
            return
        fd = os.open("/dev/tty", os.O_RDONLY | os.O_NONBLOCK)
        old_attrs = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        while not stop_event.is_set() and not interrupt_requested.is_set():
            readable, _, _ = select.select([fd], [], [], 0.05)
            if not readable:
                continue
            try:
                data = os.read(fd, 32)
            except BlockingIOError:
                continue
            if b"\x1b" in data:
                interrupt_requested.set()
                return
    except Exception:
        return
    finally:
        if fd is not None:
            if old_attrs is not None:
                with contextlib.suppress(Exception):
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            with contextlib.suppress(Exception):
                os.close(fd)


def _watch_windows_esc_keypress(
    interrupt_requested: threading.Event,
    stop_event: threading.Event,
) -> None:
    if msvcrt is None:
        return
    kbhit = getattr(msvcrt, "kbhit", None)
    getwch = getattr(msvcrt, "getwch", None)
    if not callable(kbhit) or not callable(getwch):
        return
    while not stop_event.is_set() and not interrupt_requested.is_set():
        try:
            if not kbhit():
                time.sleep(0.05)
                continue
            key = getwch()
        except Exception:
            return
        if key == "\x1b":
            interrupt_requested.set()
            return


class TerminalStreamRenderer:
    def __init__(
        self,
        console: Console,
        *,
        project_root: str | None = None,
        status: Any | None = None,
        status_started_at: float | None = None,
        palette: UiPalette | None = None,
        footer: StatusFooter | None = None,
    ) -> None:
        self.console = console
        self.project_root = project_root
        self.status = status
        self.palette = palette or DARK_PALETTE
        self.footer = footer
        self.status_started_at = (
            status_started_at if status_started_at is not None else time.monotonic()
        )
        self.status_detail = ""
        self.pending_tool_calls: dict[str, ToolCallDisplay] = {}
        self.reasoning_started = False
        self.reasoning_buffer = ""

    def __call__(self, event: DeepyStreamEvent) -> None:
        _print_stream_event(
            self.console,
            event,
            project_root=self.project_root,
            pending_tool_calls=self.pending_tool_calls,
            reasoning_sink=self,
            palette=self.palette,
        )

    def add_reasoning(self, text: str) -> None:
        if not text:
            return
        if not self.reasoning_started:
            self.console.print(
                Text.assemble(
                    ("• ", self.palette.muted),
                    (format_tool_display_label("Thinking"), f"bold {self.palette.muted}"),
                ),
            )
            self.reasoning_started = True
        self.reasoning_buffer = "printed"
        self.console.print(Text(text, style=self.palette.muted), end="")
        if self.status is not None and self.status_detail != "thinking":
            self.update_status("thinking")

    def set_tool_status(self, summary: str) -> None:
        if self.status is not None and summary:
            self.update_status(f"tool {summary}")

    def update_status(self, detail: str | None = None) -> None:
        if detail is not None:
            self.status_detail = detail
        if self.status is not None:
            self.status.update(
                _working_status_text(
                    self.status_started_at,
                    self.status_detail,
                    palette=self.palette,
                    footer=self.footer,
                )
            )

    def flush(self) -> None:
        if self.reasoning_buffer:
            self.console.print()
        self.reasoning_started = False
        self.reasoning_buffer = ""

def _handle_slash_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    loaded_skill_names: list[str] | None = None,
    settings: Settings | None = None,
    input_func: InputFunc | None = None,
    palette: UiPalette | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
) -> str | None:
    loaded_skill_names = loaded_skill_names if loaded_skill_names is not None else []
    settings = settings or Settings()
    palette = palette or resolve_ui_palette(settings.ui.theme)
    if command.name in {"exit", "quit"}:
        _print_exit_summary(console, project_root, current_session_id, settings)
        return "__exit__"
    if command.name == "help":
        console.print("/help       Show commands")
        console.print("/skills     Manage skills")
        console.print("/skills show NAME")
        console.print("/skills use NAME")
        console.print("/skill:NAME  Invoke a skill")
        console.print("/init      Create or update project AGENTS.md")
        console.print("/mcp       Show MCP server status and tools")
        console.print("/model      Select model and thinking strength")
        console.print("/input-suggestion Toggle input suggestions")
        console.print("/status     Show project status")
        console.print("/theme      Show or change UI theme")
        console.print("/reset      Delete config and run setup again")
        console.print("/sessions   List project sessions")
        console.print("/resume ID  Resume a session")
        console.print("/compact \\[focus] Compact active session context")
        console.print("/new        Start a new session")
        console.print("/exit       Quit")
        return current_session_id
    if command.name == "new":
        loaded_skill_names.clear()
        console.print("Started a new session.")
        return None
    if command.name == "resume":
        entries = list_session_entries(project_root)
        previews = _build_resume_session_previews(project_root, entries)
        if command.argument:
            selected = resolve_session_selection(entries, command.argument)
            session_id = selected.id if selected is not None else command.argument
            _resume_session(console, project_root, session_id, palette=palette)
            return session_id
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        invalid_selection = False
        if input_func is not None:
            console.print(format_resume_session_choices(previews))
            selection = input_func("Resume session number or id")
            selected = resolve_session_selection(entries, selection)
            session_id = selected.id if selected is not None else ""
            invalid_selection = bool(selection.strip()) and selected is None
        else:
            session_id = pick_resume_session(previews) or ""
            selected = resolve_session_selection(entries, session_id) if session_id else None
            invalid_selection = bool(session_id) and selected is None
        if selected is None:
            message = "Invalid session selection." if invalid_selection else "Resume canceled."
            style = palette.error if invalid_selection else palette.muted
            console.print(f"[{style}]{message}[/]")
            return current_session_id
        _resume_session(console, project_root, selected.id, palette=palette)
        return selected.id
    if command.name == "sessions":
        entries = list_session_entries(project_root)
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        for entry in entries:
            console.print(
                f"{entry.id}\tupdated={entry.updated_at}\thistory_estimate={entry.active_tokens}\t"
                f"{format_usage_line(entry.usage)}"
            )
        return current_session_id
    if command.name == "status":
        console.print(format_status_report(build_status_report(project_root, settings)))
        return current_session_id
    if command.name == "mcp":
        statuses = mcp_runtime.statuses if mcp_runtime is not None else []
        console.print(format_mcp_status(statuses))
        return current_session_id
    if command.name == "compact":
        return _handle_compact_command(
            command,
            console,
            project_root,
            current_session_id,
            settings,
            palette,
        )
    if command.name == "model":
        return _handle_model_command(
            command,
            console,
            current_session_id,
            settings,
            palette,
            input_func=input_func,
        )
    if command.name == "input-suggestion":
        return _handle_input_suggestion_command(command, console, current_session_id, settings, palette)
    if command.name == "theme":
        return _handle_theme_command(
            command,
            console,
            current_session_id,
            settings,
            palette,
            input_func=input_func,
        )
    if command.name == "reset":
        return _handle_reset_command(console, current_session_id, settings, palette)
    if command.name == "skills":
        return _handle_skills_command(
            command,
            console,
            project_root,
            current_session_id,
            loaded_skill_names,
            palette,
        )
    if command.name.startswith("skill:"):
        skill_name = command.name.removeprefix("skill:")
        skill = find_skill(project_root, skill_name)
        if skill is None:
            console.print(f"[{palette.error}]Skill not found:[/] {skill_name}")
            return current_session_id
        console.print(f"[{palette.error}]Cannot run /skill:{skill.name} from this handler.[/]")
        return current_session_id

    console.print(f"[{palette.error}]Unknown command:[/] /{command.name}")
    return current_session_id


def _handle_skills_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> str | None:
    action, _, rest = command.argument.partition(" ")
    action = action.strip().lower()
    argument = rest.strip()
    if not action:
        _run_skills_menu(console, project_root, loaded_skill_names, palette)
        return current_session_id
    if action == "list":
        console.print(format_skills_for_terminal(discover_skills(project_root)))
        return current_session_id
    if action == "show":
        if not argument:
            console.print(f"[{palette.error}]Usage:[/] /skills show NAME")
            return current_session_id
        skill = find_skill(project_root, argument)
        if skill is None:
            console.print(f"[{palette.error}]Skill not found:[/] {argument}")
            return current_session_id
        console.print(read_skill_body(skill) or "(empty skill)")
        return current_session_id
    if action == "use":
        if not argument:
            console.print(f"[{palette.error}]Usage:[/] /skills use NAME")
            return current_session_id
        skill = find_skill(project_root, argument)
        if skill is None:
            console.print(f"[{palette.error}]Skill not found:[/] {argument}")
            return current_session_id
        if skill.name not in loaded_skill_names:
            loaded_skill_names.append(skill.name)
        console.print(f"Loaded skill: {skill.name}")
        return current_session_id
    if action in {"search", "install", "uninstall", "installed", "update"}:
        changed = _handle_skill_market_command(action, argument, console, palette)
        if changed and action == "uninstall":
            loaded_skill_names[:] = [
                name for name in loaded_skill_names if name.lower() != argument.lower()
            ]
        return current_session_id
    console.print(
        f"[{palette.error}]Usage:[/] /skills [list|show NAME|use NAME|search QUERY|install NAME|"
        "uninstall NAME|installed|update NAME|update --all]"
    )
    return current_session_id


def _run_skills_menu(
    console: Console,
    project_root: Path,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> None:
    while True:
        try:
            installed_skills = _build_installed_skill_views(project_root)
        except Exception as exc:
            installed_skills = []
            console.print(f"[{palette.error}]Installed skills error:[/] {exc}")

        action = pick_skill_menu_action(
            None,
            installed_skills,
            market_loader=lambda: _load_market_skills_for_menu(project_root),
        )
        if action is None:
            return
        if action.action == "refresh":
            continue
        _handle_skill_menu_action(action, console, project_root, loaded_skill_names, palette)


def _build_installed_skill_views(project_root: Path) -> list[InstalledSkillView]:
    records = list_installed_skills()
    records_by_name = {record.name: record for record in records}
    views: list[InstalledSkillView] = []
    seen: set[str] = set()
    for skill in discover_skills(project_root):
        if skill.scope not in {"project", "user"}:
            continue
        record = records_by_name.get(skill.name)
        views.append(
            InstalledSkillView(
                name=skill.name,
                scope=record.scope if record is not None else skill.scope,
                path=record.install_path if record is not None else skill.path.parent,
                version=record.version if record is not None else "",
                installed_at=record.installed_at if record is not None else "",
                managed_by_market=record is not None,
            )
        )
        seen.add(skill.name)
    for record in records:
        if record.name in seen:
            continue
        views.append(
            InstalledSkillView(
                name=record.name,
                scope=record.scope,
                path=record.install_path,
                version=record.version,
                installed_at=record.installed_at,
                managed_by_market=True,
            )
        )
    return sorted(views, key=lambda item: (item.scope != "project", item.name))


def _load_market_skills_for_menu(project_root: Path):
    local_names = {
        skill.name
        for skill in discover_skills(project_root)
        if skill.scope in {"project", "user"}
    }
    return [
        replace(skill, installed=skill.installed or skill.name in local_names)
        for skill in search_market_skills("")
    ]


def _handle_skill_menu_action(
    action: SkillMenuAction,
    console: Console,
    project_root: Path,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> bool:
    if action.action == "choose-install-scope":
        install_scope = pick_skill_install_scope(
            action.name,
            home=Path.home(),
            project_root=project_root,
        )
        if install_scope is None:
            return False
        try:
            record = install_market_skill(
                action.name,
                scope=install_scope.scope,
                project_root=project_root,
            )
        except Exception as exc:
            console.print(f"[{palette.error}]Skill market error:[/] {exc}")
            return False
        console.print(f"Installed skill: {record.name} ({record.scope}) -> {record.install_path}")
        return True
    if action.action == "update":
        return _handle_skill_market_command("update", action.name, console, palette)
    if action.action == "uninstall":
        changed = _handle_skill_market_command("uninstall", action.name, console, palette)
        if changed:
            loaded_skill_names[:] = [
                name for name in loaded_skill_names if name.lower() != action.name.lower()
            ]
        return changed
    if action.action == "remove-local":
        return _remove_local_skill(action, console, loaded_skill_names, palette)
    if action.action == "show":
        if action.market_skill is not None and action.path is None:
            market_skill = action.market_skill
            show_skill_detail_view(
                SkillDetailView(
                    name=market_skill.name,
                    scope="market",
                    version=market_skill.version,
                    description=market_skill.description,
                    uploaded_at=market_skill.uploaded_at,
                    sha256=market_skill.sha256,
                    installed=market_skill.installed,
                    markdown=True,
                )
            )
            return False
        if action.path is not None:
            skill = SkillInfo(
                name=action.name,
                path=action.path / "SKILL.md",
                scope=action.scope or "user",
            )
        else:
            skill = find_skill(project_root, action.name)
        if skill is None:
            console.print(f"[{palette.error}]Skill not installed:[/] {action.name}")
            return False
        show_skill_detail_view(
            SkillDetailView(
                name=skill.name,
                body=read_skill_body(skill) or "(empty skill)",
                scope=skill.scope,
                path=skill.path.parent,
                version=action.version,
                installed_at=action.installed_at,
                managed_by_market=action.managed_by_market,
                markdown=True,
            )
        )
        return False
    return False


def _remove_local_skill(
    action: SkillMenuAction,
    console: Console,
    loaded_skill_names: list[str],
    palette: UiPalette,
) -> bool:
    if action.path is None:
        console.print(f"[{palette.error}]Skill path is unknown:[/] {action.name}")
        return False
    skill_path = action.path / "SKILL.md"
    if not action.path.is_dir() or not skill_path.is_file():
        console.print(f"[{palette.error}]Skill path is invalid:[/] {action.path}")
        return False
    if action.path.parent.name != "skills" or action.path.parent.parent.name != ".agents":
        console.print(f"[{palette.error}]Refusing to remove unexpected path:[/] {action.path}")
        return False
    shutil.rmtree(action.path)
    loaded_skill_names[:] = [
        name for name in loaded_skill_names if name.lower() != action.name.lower()
    ]
    console.print(f"Removed local skill: {action.name} ({action.scope}) -> {action.path}")
    return True


def _handle_skill_market_command(
    action: str,
    argument: str,
    console: Console,
    palette: UiPalette,
) -> bool:
    try:
        if action == "search":
            skills = search_market_skills(argument)
            if not skills:
                console.print(f"[{palette.muted}]No market skills found.[/]")
                return False
            for skill in skills:
                marker = " (installed)" if skill.installed else ""
                desc = f" - {skill.description}" if skill.description else ""
                uploaded = f" uploaded={skill.uploaded_at}" if skill.uploaded_at else ""
                console.print(f"{skill.name}{marker}{desc}{uploaded}")
            return False
        if action == "install":
            if not argument:
                console.print(f"[{palette.error}]Usage:[/] /skills install NAME")
                return False
            record = install_market_skill(argument)
            console.print(f"Installed skill: {record.name} -> {record.install_path}")
            return True
        if action == "uninstall":
            if not argument:
                console.print(f"[{palette.error}]Usage:[/] /skills uninstall NAME")
                return False
            removed = uninstall_market_skill(argument)
            console.print(f"Uninstalled skill: {removed}")
            return True
        if action == "installed":
            records = list_installed_skills()
            if not records:
                console.print(f"[{palette.muted}]No market-installed skills.[/]")
                return False
            for record in records:
                console.print(f"{record.name}\t{record.install_path}\tinstalled={record.installed_at}")
            return False
        if action == "update":
            records = list_installed_skills()
            if argument == "--all":
                if not records:
                    console.print(f"[{palette.muted}]No market-installed skills.[/]")
                    return False
                for record in records:
                    status, updated = update_market_skill(record.name)
                    console.print(f"{updated.name}: {status}")
                return True
            if not argument:
                console.print(f"[{palette.error}]Usage:[/] /skills update NAME|--all")
                return False
            status, updated = update_market_skill(argument)
            console.print(f"{updated.name}: {status}")
            return True
    except Exception as exc:
        console.print(f"[{palette.error}]Skill market error:[/] {exc}")
    return False


def _handle_compact_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    if not current_session_id:
        console.print(f"[{palette.muted}]No active session to compact.[/]")
        return current_session_id
    session = DeepyJsonlSession.open(project_root, current_session_id)
    try:
        items = asyncio.run(session.get_items())
    except Exception as exc:
        console.print(f"[{palette.error}]Failed to read session:[/] {exc}")
        return current_session_id
    if not items:
        console.print(f"[{palette.muted}]The context is empty.[/]")
        return current_session_id
    console.print(f"[{palette.muted}]Compacting context...[/]")
    manager = DeepySessionManager(project_root=project_root, settings=settings, active_session_id=current_session_id)
    try:
        result = asyncio.run(
            manager.compact_session(
                current_session_id,
                focus_instruction=command.argument or None,
            )
        )
    except ContextCompactionError as exc:
        console.print(f"[{palette.error}]Compact failed:[/] {exc}")
        console.print(f"[{palette.muted}]Original session left unchanged.[/]")
        return current_session_id
    except Exception as exc:
        console.print(f"[{palette.error}]Compact failed:[/] {exc}")
        console.print(f"[{palette.muted}]Original session left unchanged.[/]")
        return current_session_id
    if not result.compacted:
        console.print(f"[{palette.muted}]{result.message or 'There is no context to compact.'}[/]")
        return current_session_id
    console.print(
        f"[{palette.info}]Context compacted:[/] "
        f"{result.before_tokens:,} -> {result.after_tokens:,} tokens · "
        f"preserved {result.preserved_item_count} items"
    )
    return current_session_id


def _handle_theme_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    theme = command.argument
    if not theme:
        console.print(f"Current theme: {settings.ui.theme}")
        selected = _prompt_for_theme_selection(
            settings.ui.theme,
            console=console,
            input_func=input_func,
        )
        if selected is None:
            console.print("Theme unchanged.")
            return current_session_id
        theme = selected
    if theme not in UI_THEMES:
        console.print(f"[{palette.error}]Usage:[/] /theme auto|dark|light")
        return current_session_id
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist theme: config path is unknown.[/]")
        return current_session_id
    update_config_theme(settings.path, theme)
    console.print(f"Saved UI theme: {theme}")
    console.print("Restart Deepy to apply the theme everywhere.")
    return current_session_id


def _handle_model_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    parts = command.argument.split()
    if not parts:
        return _handle_interactive_model_selection(
            console,
            current_session_id,
            settings,
            palette,
            input_func=input_func,
        )
    action = parts[0].lower()
    if action == "list" and len(parts) == 1:
        _print_model_choices(console)
        return current_session_id
    if action == "set" and len(parts) in {2, 3}:
        model = parts[1]
        if not is_supported_deepseek_model(model):
            console.print(f"[{palette.error}]Invalid model:[/] {model}")
            _print_model_usage(console, palette)
            return current_session_id
        reasoning_mode = parts[2] if len(parts) == 3 else None
        if reasoning_mode is not None and not is_valid_reasoning_mode(reasoning_mode):
            console.print(f"[{palette.error}]Invalid reasoning mode:[/] {reasoning_mode}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    if action in {"reasoning", "thinking"} and len(parts) == 2:
        reasoning_mode = parts[1]
        if not is_valid_reasoning_mode(reasoning_mode):
            console.print(f"[{palette.error}]Invalid reasoning mode:[/] {reasoning_mode}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            reasoning_mode=reasoning_mode,
        )
    _print_model_usage(console, palette)
    return current_session_id


def _handle_input_suggestion_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    if command.argument.strip():
        console.print(f"[{palette.error}]Usage:[/] /input-suggestion")
        return current_session_id
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist input suggestion setting: config path is unknown.[/]")
        return current_session_id
    enabled = not settings.ui.input_suggestions_enabled
    update_config_input_suggestions_enabled(settings.path, enabled)
    console.print(f"Input suggestions {'enabled' if enabled else 'disabled'}.")
    return current_session_id


def _handle_interactive_model_selection(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    console.print(
        f"Current model: {settings.model.name} · reasoning: {settings.model.reasoning_mode}"
    )
    selected_model = _prompt_for_model_selection(
        settings.model.name,
        console=console,
        input_func=input_func,
    )
    if selected_model is None:
        console.print("Model unchanged.")
        return current_session_id
    selected_reasoning = _prompt_for_reasoning_mode_selection(
        settings.model.reasoning_mode,
        console=console,
        input_func=input_func,
    )
    if selected_reasoning is None:
        console.print("Model unchanged.")
        return current_session_id
    return _save_model_settings(
        console,
        current_session_id,
        settings,
        palette,
        model=selected_model,
        reasoning_mode=selected_reasoning,
    )


def _save_model_settings(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    *,
    model: str | None = None,
    reasoning_mode: str | None = None,
) -> str | None:
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist model settings: config path is unknown.[/]")
        return current_session_id
    try:
        update_config_model_settings(
            settings.path,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    except ValueError as exc:
        console.print(f"[{palette.error}]{exc}[/]")
        return current_session_id
    active_model = model or settings.model.name
    active_reasoning = reasoning_mode or settings.model.reasoning_mode
    console.print(f"Saved model: {active_model} · reasoning: {active_reasoning}")
    return current_session_id


def _print_model_choices(console: Console) -> None:
    console.print("Available models:")
    for index, model in enumerate(DEEPSEEK_MODEL_CATALOG, 1):
        console.print(f"{index}. {model.name} - {model.description}")
    console.print("Reasoning modes:")
    for index, (value, _label) in enumerate(REASONING_MODE_CHOICES, 1):
        console.print(f"{index}. {value}")


def _print_model_usage(console: Console, palette: UiPalette) -> None:
    console.print(
        f"[{palette.error}]Usage:[/] /model | /model list | "
        "/model set deepseek-v4-pro|deepseek-v4-flash [none|high|max] | "
        "/model reasoning none|high|max"
    )


def _prompt_for_model_selection(
    default: str,
    *,
    console: Console,
    input_func: InputFunc | None = None,
) -> str | None:
    if input_func is None:
        return pick_model(default)
    _print_model_choices(console)
    value = input_func("Model number or name").strip()
    if not value:
        return None
    return _model_from_selection(value)


def _prompt_for_reasoning_mode_selection(
    default: str,
    *,
    console: Console,
    input_func: InputFunc | None = None,
) -> str | None:
    if input_func is None:
        return pick_reasoning_mode(default)
    _print_reasoning_choices(console)
    value = input_func("Thinking strength number or name").strip()
    if not value:
        return None
    return _reasoning_mode_from_selection(value)


def _model_from_selection(value: str) -> str | None:
    normalized = value.strip()
    by_number = {str(index): model.name for index, model in enumerate(DEEPSEEK_MODEL_CATALOG, 1)}
    if normalized in by_number:
        return by_number[normalized]
    return normalized if is_supported_deepseek_model(normalized) else None


def _reasoning_mode_from_selection(value: str) -> str | None:
    normalized = value.strip().lower()
    by_number = {str(index): mode for index, (mode, _label) in enumerate(REASONING_MODE_CHOICES, 1)}
    if normalized in by_number:
        return by_number[normalized]
    return normalized if is_valid_reasoning_mode(normalized) else None


def _print_reasoning_choices(console: Console) -> None:
    console.print("Thinking strength:")
    for index, (value, label) in enumerate(REASONING_MODE_CHOICES, 1):
        console.print(f"{index}. {label}")


def _print_theme_choices(console: Console) -> None:
    console.print("Available themes:")
    for index, (_theme, label) in enumerate(THEME_CHOICES, 1):
        console.print(f"{index}. {label}")


def _prompt_for_theme_selection(
    default: str,
    *,
    console: Console,
    input_func: InputFunc | None = None,
) -> str | None:
    if input_func is None:
        return pick_theme(default)
    _print_theme_choices(console)
    value = input_func("Theme number or name").strip()
    if not value:
        return None
    return _theme_from_selection(value)


def _theme_from_selection(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in UI_THEMES:
        return normalized
    return {"1": "auto", "2": "dark", "3": "light"}.get(normalized)


def _handle_reset_command(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot reset config: config path is unknown.[/]")
        return current_session_id
    if settings.path.exists():
        settings.path.unlink()
        console.print(f"Removed {settings.path}")
    else:
        console.print(f"No existing config at {settings.path}")
    console.print("Starting Deepy configuration setup...")
    _run_interactive_config_setup(settings.path, previous=settings, console=console)
    console.print(f"Wrote {settings.path}")
    return current_session_id


def _run_interactive_config_setup(
    config_path: Path,
    *,
    previous: Settings,
    console: Console,
) -> None:
    console.print("DeepSeek API keys: https://platform.deepseek.com/api_keys")
    api_key = _prompt_config_value("API key", default="", is_password=True)
    model = _prompt_config_value("Model", default=previous.model.name)
    base_url = _prompt_config_value("Base URL", default=previous.model.base_url)
    theme = _prompt_theme_config_value(default=previous.ui.theme, console=console)
    write_config(
        config_path,
        api_key=api_key,
        model=model,
        base_url=base_url,
        theme=theme,
    )


def _prompt_theme_config_value(*, default: str, console: Console) -> str:
    _print_theme_choices(console)
    value = _prompt_config_value("UI theme number", default=ui_theme_number(default))
    return ui_theme_from_selection(value, default=default)


def _prompt_config_value(label: str, *, default: str, is_password: bool = False) -> str:
    from prompt_toolkit import PromptSession

    prompt = f"{label}"
    if default and not is_password:
        prompt += f" [{default}]"
    prompt += ": "
    value = PromptSession().prompt(prompt, default="" if is_password else default, is_password=is_password)
    value = value.strip()
    return value or default


def _resume_session(
    console: Console,
    project_root: Path,
    session_id: str,
    *,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    console.print(Text.assemble(("Resuming session ", palette.muted), (session_id, palette.info)))
    _print_session_history(console, project_root, session_id, palette=palette)


def _build_resume_session_previews(
    project_root: Path,
    entries: list[SessionEntry],
) -> list[ResumeSessionPreview]:
    previews: list[ResumeSessionPreview] = []
    for entry in entries:
        items = _load_session_items(project_root, entry.id)
        previews.append(
            ResumeSessionPreview(
                id=entry.id,
                title=_session_title(items),
                status=_session_status(items),
                updated_at=entry.updated_at,
                active_tokens=entry.active_tokens,
            )
        )
    return previews


def _print_session_history(
    console: Console,
    project_root: Path,
    session_id: str,
    *,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    items = _load_session_items(project_root, session_id)
    if not items:
        console.print(f"[{palette.muted}]No visible history for this session.[/]")
        return

    console.print(Text("History", style=f"bold {palette.muted}"))
    renderer = TerminalStreamRenderer(console, project_root=str(project_root), palette=palette)
    for item in items:
        _print_history_item(console, item, renderer, palette=palette)
    renderer.flush()


def _print_history_item(
    console: Console,
    item: dict[str, Any],
    renderer: TerminalStreamRenderer,
    *,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    item_type = _item_type(item)
    role = _role(item)

    if item_type == "reasoning":
        renderer(DeepyStreamEvent(kind="reasoning_delta", text=_reasoning_text(item)))
        return

    if item_type == "function_call":
        renderer(_history_tool_call_event(item))
        return

    if item_type == "function_call_output":
        renderer(_history_tool_output_event(item))
        return

    if role == "tool":
        renderer(_history_tool_output_event(item))
        return

    if role == "user":
        renderer.flush()
        _print_user_input(console, _item_text(item), palette=palette)
        return

    if role == "assistant":
        text = _item_text(item)
        tool_calls = _chat_tool_calls(item)
        if text.strip():
            renderer.flush()
            _print_assistant_output(console, text, palette=palette)
        for tool_call in tool_calls:
            renderer(_history_tool_call_event(tool_call))
        return


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


def _load_session_items(project_root: Path, session_id: str) -> list[dict[str, Any]]:
    try:
        return asyncio.run(DeepyJsonlSession.open(project_root, session_id).get_items())
    except Exception:
        return []


def _session_title(items: list[dict[str, Any]]) -> str:
    for item in items:
        if _role(item) == "user":
            text = _item_text(item)
            if text.strip():
                return text
    for item in items:
        text = _item_text(item)
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


def _is_waiting_tool_output(item: dict[str, Any]) -> bool:
    if _item_type(item) != "function_call_output" and _role(item) != "tool":
        return False
    return parse_tool_output(_tool_output_text(item)).await_user_response


def _is_failed_tool_output(item: dict[str, Any]) -> bool:
    if _item_type(item) != "function_call_output" and _role(item) != "tool":
        return False
    return parse_tool_output(_tool_output_text(item)).ok is False


def _item_text(item: dict[str, Any]) -> str:
    if "content" in item:
        return _content_text(item["content"])
    if "text" in item:
        return _content_text(item["text"])
    if "output" in item:
        return _content_text(item["output"])
    return ""


def _reasoning_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("content", "summary", "text"):
        if key in item:
            text = _content_text(item[key])
            if text.strip():
                parts.append(text)
    return "\n".join(parts)


def _tool_output_text(item: dict[str, Any]) -> str:
    if "output" in item:
        return _content_text(item["output"])
    content = item.get("content")
    if isinstance(content, list):
        return json_utils.dumps(content)
    return _item_text(item)


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for part in value:
            text = _content_text_part(part)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if value is None:
        return ""
    value_dict = _string_key_dict(value)
    if value_dict is not None:
        text = _content_text_part(value_dict)
        return text or json_utils.dumps(value_dict)
    if isinstance(value, dict):
        return json_utils.dumps(value)
    return str(value)


def _content_text_part(part: object) -> str:
    if isinstance(part, str):
        return part
    part_dict = _string_key_dict(part)
    if part_dict is None:
        return ""
    for key in ("text", "input_text", "output_text", "refusal"):
        value = part_dict.get(key)
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


def _string_key_dict(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


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


def _print_exit_summary(
    console: Console,
    project_root: Path,
    session_id: str | None,
    settings: Settings,
) -> None:
    session_entry: SessionEntry | None = None
    messages: list[dict[str, object]] = []
    if session_id:
        session_entry = next(
            (entry for entry in list_session_entries(project_root) if entry.id == session_id),
            None,
        )
        try:
            messages = asyncio.run(DeepyJsonlSession.open(project_root, session_id).get_items())
        except Exception:
            messages = []
    console.print(
        build_exit_summary_text(
            session=session_entry,
            messages=messages,
            model=settings.model.name,
        )
    )


def _print_usage_footer(
    console: Console,
    summary: RunSummary,
    *,
    settings: Settings | None = None,
    project_root: Path | None = None,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    if summary.usage.known:
        duration = _format_duration_ms(summary.duration_ms) if summary.duration_ms > 0 else ""
        prefix = f"time {duration} · " if duration else ""
        console.print(
            f"[{palette.muted}]turn Token Usage[/] {prefix}{_format_turn_usage_line(summary.usage)}"
        )
    elif summary.duration_ms > 0:
        console.print(f"[{palette.muted}]turn time[/] {_format_duration_ms(summary.duration_ms)}")


def _format_context_footer(
    session_id: str | None,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
) -> str:
    return _build_status_footer(
        session_id,
        project_root=project_root,
        settings=settings,
        mcp_runtime=mcp_runtime,
    ).plain


def _build_status_footer(
    session_id: str | None,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
    active_work: str | None = None,
) -> StatusFooter:
    if settings is None:
        return StatusFooter(())

    segments = [
        StatusFooterSegment(
            f"model {settings.model.name}[{settings.model.reasoning_mode}]",
            "identity",
        ),
    ]
    if project_root is not None:
        segments.append(StatusFooterSegment(f"cwd {format_home_relative_path(project_root)}", "metadata"))
        if has_agents_instructions(project_root):
            segments.append(StatusFooterSegment("[AGENTS.md]", "loaded"))
        if mcp_runtime is not None and mcp_runtime.active_servers:
            segments.append(StatusFooterSegment(f"mcp {len(mcp_runtime.active_servers)}", "loaded"))
    else:
        segments.append(StatusFooterSegment("cwd unknown", "metadata"))

    window_tokens = settings.context.window_tokens
    compact_threshold = settings.context.resolved_compact_threshold
    if window_tokens <= 0:
        segments.append(StatusFooterSegment("ctx unknown", "context"))
        return StatusFooter(tuple(segments)).with_active(active_work)

    session_entry = _session_entry(project_root, session_id)
    segments.append(
        StatusFooterSegment(
            _format_context_window_status(session_entry, window_tokens, compact_threshold),
            "context",
        )
    )

    return StatusFooter(tuple(segments)).with_active(active_work)


def _format_context_window_status(
    session_entry: SessionEntry | None,
    window_tokens: int,
    compact_threshold: int,
) -> str:
    window_text = _format_token_count_short(window_tokens)
    if session_entry is not None and session_entry.latest_context_window_tokens is not None:
        used_tokens = session_entry.latest_context_window_tokens
    else:
        usage_payload = session_entry.usage if session_entry is not None else None
        usage = (
            context_window_usage(usage_payload)
            if isinstance(usage_payload, dict) and usage_payload.get("request_usage_entries")
            else None
        )
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


def _session_entry(project_root: Path | None, session_id: str | None) -> SessionEntry | None:
    if not session_id:
        return None
    if project_root is None:
        return None
    try:
        entries = list_session_entries(project_root)
    except Exception:
        return None
    entry = next((item for item in entries if item.id == session_id), None)
    return entry


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


def _format_turn_usage_line(usage: TokenUsage) -> str:
    prefix = f"requests {usage.requests:,} · " if usage.requests > 0 else ""
    return f"{prefix}{format_usage_line(usage)}"


def _refresh_working_status(
    renderer: TerminalStreamRenderer,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(0.2):
        renderer.update_status()


@contextlib.contextmanager
def _status_display(
    console: Console,
    initial_status: Text,
    *,
    palette: UiPalette,
    anchor_output: bool = False,
    anchor_output_lines: int = 0,
):
    if _should_use_bottom_status_overlay(console):
        status = _TerminalBottomStatus(console, palette=palette)
        status.start(anchor_output=anchor_output, anchor_output_lines=anchor_output_lines)
        status.update(initial_status)
        try:
            yield status
        finally:
            status.clear()
        return

    yield _SilentStatus()


def _should_use_bottom_status_overlay(console: Console) -> bool:
    isatty = getattr(console.file, "isatty", None)
    return bool(callable(isatty) and isatty())


class _TerminalBottomStatus:
    def __init__(
        self,
        console: Console,
        *,
        palette: UiPalette,
    ) -> None:
        self.console = console
        self.palette = palette
        self.rows = 0
        self.columns = 0

    def start(self, *, anchor_output: bool = False, anchor_output_lines: int = 0) -> None:
        self.columns, self.rows = shutil.get_terminal_size((80, 24))
        if self.rows <= 1:
            return
        scroll_bottom = self.rows - 1
        scroll_lines = max(anchor_output_lines, 2 if anchor_output else 0)
        if scroll_lines:
            output_row = max(scroll_bottom - scroll_lines + 1, 1)
            scroll_text = "\n" * scroll_lines
            self.console.file.write(
                f"\x1b[1;{scroll_bottom}r\x1b[{scroll_bottom};1H"
                f"{scroll_text}"
                f"\x1b[{output_row};1H"
            )
        else:
            self.console.file.write(f"\x1b7\x1b[1;{scroll_bottom}r\x1b[{scroll_bottom};1H\x1b8")
        self.console.file.flush()

    def update(self, status: Text) -> None:
        columns, rows = shutil.get_terminal_size((80, 24))
        self.columns = columns
        self.rows = rows
        if rows <= 1:
            return
        self._write_line(rows, status.plain, _terminal_runtime_status_style(self.palette))
        self.console.file.flush()

    def clear(self) -> None:
        columns, rows = shutil.get_terminal_size((80, 24))
        self.columns = columns
        self.rows = rows
        if rows <= 1:
            return
        self.console.file.write("\x1b7\x1b[r")
        self.console.file.write(f"\x1b[{rows};1H\x1b[2K")
        self.console.file.write("\x1b8")
        self.console.file.flush()

    def _write_line(self, row: int, text: str, style: str) -> None:
        width = max(self.columns - 1, 1)
        line = _truncate_status_line(text, max_width=width)
        padded = line.ljust(width)
        self.console.file.write(f"\x1b7\x1b[{row};1H\x1b[2K{style}{padded}\x1b[0m\x1b8")


class _SilentStatus:
    def update(self, status: Text) -> None:
        return None


def _terminal_runtime_status_style(palette: UiPalette) -> str:
    foreground = _hex_color(palette.toolbar_background) or "#161821"
    background = _hex_color(palette.warning) or "#facc15"
    return _terminal_ansi_style(foreground=foreground, background=background, bold=True)


def _terminal_ansi_style(
    *,
    foreground: str = "",
    background: str = "",
    bold: bool = False,
) -> str:
    codes: list[str] = []
    codes.append("1" if bold else "22")
    if foreground:
        codes.append(_ansi_rgb("38", foreground))
    if background:
        codes.append(_ansi_rgb("48", background))
    return f"\x1b[{';'.join(codes)}m" if codes else ""


def _hex_color(style: str) -> str:
    return next((part for part in style.split() if part.startswith("#") and len(part) == 7), "")


def _ansi_rgb(prefix: str, color: str) -> str:
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f"{prefix};2;{red};{green};{blue}"


def _truncate_status_line(text: str, *, max_width: int) -> str:
    if len(text) <= max_width:
        return text
    if max_width <= 1:
        return text[:max_width]
    return f"{text[: max_width - 1]}…"


def _working_status_text(
    started_at: float,
    detail: str = "",
    *,
    palette: UiPalette | None = None,
    footer: StatusFooter | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    elapsed = _format_duration_ms(int((time.monotonic() - started_at) * 1000)) or "0s"
    if footer is not None and footer.segments:
        return _runtime_status_text(
            elapsed=elapsed,
            detail=detail or "status working",
            spinner=_runtime_spinner_frame(started_at),
            palette=palette,
        )
    text = Text.assemble(
        ("Working ", f"bold {palette.muted}"),
        (f"({elapsed} · esc to interrupt)", palette.muted),
    )
    if detail:
        text.append(" · ", style=palette.muted)
        text.append(detail, style=palette.muted)
    return text


def _local_command_status_text(
    command: str,
    started_at: float,
    *,
    palette: UiPalette | None = None,
    footer: StatusFooter | None = None,
) -> Text:
    palette = palette or DARK_PALETTE
    elapsed = _format_duration_ms(int((time.monotonic() - started_at) * 1000)) or "0s"
    if footer is not None and footer.segments:
        text = _runtime_status_text(
            elapsed=elapsed,
            detail="local command",
            spinner=_runtime_spinner_frame(started_at),
            palette=palette,
        )
        text.append(" · ", style=palette.toolbar_separator)
        text.append(command, style=palette.toolbar_metadata)
        return text
    text = Text.assemble(
        ("Running local command ", f"bold {palette.muted}"),
        (f"({elapsed})", palette.muted),
    )
    text.append(" · ", style=palette.muted)
    text.append(command, style=palette.muted)
    return text


def _runtime_status_text(
    *,
    elapsed: str,
    detail: str,
    spinner: str = "",
    palette: UiPalette,
) -> Text:
    parts: list[tuple[str, str]] = []
    style = _runtime_text_style(palette)
    if spinner:
        parts.extend([(spinner, style), (" ", style)])
    parts.extend(
        [
            ("time ", style),
            (elapsed, style),
            (" · ", style),
            ("esc to interrupt", style),
        ]
    )
    text = Text.assemble(*parts)
    if detail:
        text.append(" · ", style=style)
        text.append(detail, style=style)
    return text


def _runtime_text_style(palette: UiPalette) -> str:
    return f"bold {palette.toolbar_background}"


def _runtime_spinner_frame(started_at: float) -> str:
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    index = int(max(0.0, time.monotonic() - started_at) * 10) % len(frames)
    return frames[index]


def _format_duration_ms(duration_ms: int) -> str:
    seconds = max(0, int(duration_ms // 1000))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def _print_submitted_user_input(console: Console, text: str, *, palette: UiPalette | None = None) -> bool:
    _clear_submitted_prompt_echo(console, text)
    _print_user_input(console, text, palette=palette)
    return _submitted_prompt_needs_status_anchor(console, text)


def _submitted_prompt_needs_status_anchor(console: Console, text: str) -> bool:
    if not text.strip() or not _should_use_bottom_status_overlay(console):
        return False
    rows = shutil.get_terminal_size((80, 24)).lines
    cursor_row = _terminal_cursor_row(console)
    return cursor_row is not None and cursor_row >= rows


def _clear_submitted_prompt_echo(console: Console, text: str) -> None:
    if not text.strip():
        return
    file = getattr(console, "file", None)
    if file is None:
        return
    isatty = getattr(file, "isatty", None)
    if not callable(isatty) or not isatty():
        return

    rows = _submitted_prompt_echo_rows(text, _terminal_columns(console))
    for _ in range(rows):
        file.write("\x1b[1A\x1b[2K")
    file.write("\r")
    file.flush()


def _terminal_columns(console: Console) -> int:
    fallback = (max(1, console.width), 24)
    return max(1, shutil.get_terminal_size(fallback).columns)


def _terminal_cursor_row(console: Console, *, timeout: float = 0.03) -> int | None:
    if termios is None or tty is None or not Path("/dev/tty").exists():
        return None
    file = getattr(console, "file", None)
    if file is None:
        return None
    isatty = getattr(file, "isatty", None)
    if not callable(isatty) or not isatty():
        return None

    fd: int | None = None
    old_attrs: list[Any] | None = None
    try:
        fd = os.open("/dev/tty", os.O_RDONLY | os.O_NONBLOCK)
        old_attrs = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        file.write("\x1b[6n")
        file.flush()
        deadline = time.monotonic() + timeout
        data = b""
        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], max(0.0, deadline - time.monotonic()))
            if not readable:
                continue
            try:
                chunk = os.read(fd, 32)
            except BlockingIOError:
                continue
            if not chunk:
                continue
            data += chunk
            row = _cursor_row_from_terminal_response(data)
            if row is not None:
                return row
    except Exception:
        return None
    finally:
        if fd is not None:
            if old_attrs is not None:
                with contextlib.suppress(Exception):
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            with contextlib.suppress(Exception):
                os.close(fd)
    return None


def _cursor_row_from_terminal_response(data: bytes) -> int | None:
    match = re.search(rb"\x1b\[(\d+);\d+R", data)
    if match is None:
        return None
    return int(match.group(1))


def _submitted_prompt_echo_rows(text: str, columns: int) -> int:
    lines = text.rstrip("\n").split("\n") or [""]
    return sum(
        measure_text_rows(line, width=columns, initial_column=2 if index == 0 else 0)
        for index, line in enumerate(lines)
    )


def _print_user_input(console: Console, text: str, *, palette: UiPalette | None = None) -> None:
    palette = palette or DARK_PALETTE
    if not text.strip():
        return
    lines = text.rstrip().splitlines() or [text.rstrip()]
    rendered = Text()
    for index, line in enumerate(lines):
        if index:
            rendered.append("\n")
            rendered.append("  ", style=palette.user)
        else:
            rendered.append("> ", style=palette.user)
        rendered.append(line, style=palette.user)
    console.print(rendered)


def _print_assistant_output(
    console: Console,
    text: str,
    *,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    if not text.strip():
        return
    console.print()
    console.print(f"[bold {palette.assistant}]Deepy[/]")
    console.print(render_markdown(text.rstrip(), palette=palette, width=console.width))


def _print_stream_event(
    console: Console,
    event: DeepyStreamEvent,
    *,
    project_root: str | None = None,
    pending_tool_calls: dict[str, ToolCallDisplay] | None = None,
    reasoning_sink: TerminalStreamRenderer | None = None,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    if event.kind in {"text_delta", "message"}:
        return
    if event.kind == "reasoning_delta":
        if reasoning_sink is not None:
            reasoning_sink.add_reasoning(event.text)
        return
    if event.kind == "tool_call":
        if reasoning_sink is not None:
            reasoning_sink.flush()
        summary = format_tool_call_summary(
            event.name or "tool",
            _string_payload(event.payload.get("arguments")),
            project_root=project_root,
        )
        if pending_tool_calls is not None:
            call_id = _string_payload(event.payload.get("call_id"))
            if call_id:
                pending_tool_calls[call_id] = ToolCallDisplay(
                    summary=summary,
                    name=event.name or "tool",
                )
                if reasoning_sink is not None:
                    reasoning_sink.set_tool_status(summary)
        return
    if event.kind == "tool_output":
        if reasoning_sink is not None:
            reasoning_sink.flush()
        view = parse_tool_output(event.text)
        call_id = _string_payload(event.payload.get("call_id"))
        call = pending_tool_calls.pop(call_id, None) if pending_tool_calls is not None else None
        call_summary = call.summary if call is not None else ""
        summary = format_tool_progress_summary(call_summary, event.text)
        console.print(_status_line(summary, status_style(view.ok, palette)))
        if _should_print_tool_output_debug(view):
            console.print(Text("Tool output JSON:", style=palette.muted))
            console.print(Text(_format_tool_output_debug(event.text), style=palette.muted))
        shell_output = render_shell_output_block(event.text, palette=palette)
        if shell_output:
            console.print(shell_output)
        todo_board = render_todo_board(event.text, palette=palette, width=console.width)
        if todo_board:
            console.print(todo_board)
        diff = render_tool_diff_preview(event.text, palette=palette, width=console.width)
        if diff:
            console.print(diff)
        return
    if event.kind == "agent_updated":
        return
    if event.kind == "usage":
        return
    if event.kind == "status":
        console.print(_status_line(event.text, palette.info))
        return


def _string_payload(value: object) -> str:
    return value if isinstance(value, str) else ""


def _should_print_tool_output_debug(view: object) -> bool:
    return os.environ.get("DEEPY_DEBUG_TOOL_OUTPUT", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
        "all",
    }


def _format_tool_output_debug(output: str) -> str:
    try:
        parsed = json_utils.loads(output)
    except json_utils.JSONDecodeError:
        return output
    return json_utils.dumps_pretty(parsed)


def _status_line(text: str, style: str) -> Text:
    label_match = re.match(r"(\[[^\]]+\])(\s?.*)", text, flags=re.DOTALL)
    if label_match:
        label, detail = label_match.groups()
        return Text.assemble(
            ("• ", style),
            (label, f"bold underline {style}"),
            (detail, style),
        )
    return Text.assemble(("• ", style), (text, style))


def _collect_pending_question_response(
    console: Console,
    pending_questions: list[dict[str, object]],
    input_func: InputFunc | None = None,
) -> str:
    questions = normalize_questions(pending_questions)
    if not questions:
        return ""
    answers: dict[str, str] = {}
    chooser = input_func or (lambda prompt: console.input(f"{prompt}: "))
    for question in questions:
        answer = _prompt_for_question(console, question, chooser)
        if answer is None:
            return format_ask_user_question_decline()
        answers[question.question] = answer
    return format_ask_user_question_answers(answers)


def _prompt_for_question(
    console: Console,
    question: AskUserQuestionItem,
    input_func: InputFunc,
) -> str | None:
    options = build_options(question)
    console.print(f"\n[bold]Question:[/bold] {question.question}")
    for index, option in enumerate(options, 1):
        detail = f" - {option.description}" if option.description else ""
        console.print(f"{index}. {option.label}{detail}")
    prompt = (
        "Answer numbers separated by commas, custom text, or empty to decline"
        if question.multi_select
        else "Answer number, custom text, or empty to decline"
    )
    raw_answer = input_func(prompt).strip()
    if not raw_answer:
        return None
    direct_option = None if question.multi_select else _option_from_token(options, raw_answer)
    if direct_option is not None and direct_option.is_other:
        custom_answer = input_func(_custom_answer_prompt(direct_option)).strip()
        return build_answer_for_question(question, direct_option, [], custom_answer)
    if question.multi_select and _multi_select_needs_custom_text(options, raw_answer):
        custom_answer = input_func(_custom_answer_prompt(options[-1])).strip()
        raw_answer = f"{raw_answer}, {custom_answer}" if custom_answer else raw_answer
    return _answer_question_from_text(question, raw_answer)


def _answer_question_from_text(question: AskUserQuestionItem, raw_answer: str) -> str | None:
    options = build_options(question)
    if question.multi_select:
        selected_values: list[str] = []
        custom_values: list[str] = []
        for token in [part.strip() for part in raw_answer.split(",") if part.strip()]:
            option = _option_from_token(options, token)
            if option is not None:
                selected_values.append(option.value)
            else:
                custom_values.append(token)
        if custom_values:
            selected_values.append(OTHER_VALUE)
        return build_answer_for_question(
            question,
            None,
            selected_values,
            ", ".join(custom_values),
        )

    option = _option_from_token(options, raw_answer)
    if option is None:
        option = next((item for item in options if item.value == OTHER_VALUE), None)
    other_text = raw_answer if option is not None and option.is_other else ""
    return build_answer_for_question(question, option, [], other_text)


def _multi_select_needs_custom_text(
    options: list[AskUserQuestionOptionEntry],
    raw_answer: str,
) -> bool:
    tokens = [part.strip() for part in raw_answer.split(",") if part.strip()]
    saw_other = False
    saw_custom_text = False
    for token in tokens:
        option = _option_from_token(options, token)
        if option is not None and option.is_other:
            saw_other = True
        elif option is None:
            saw_custom_text = True
    return saw_other and not saw_custom_text


def _custom_answer_prompt(option: AskUserQuestionOptionEntry) -> str:
    return "自定义回答" if option.label.startswith("自定义") else "Custom answer"


def _option_from_token(
    options: list[AskUserQuestionOptionEntry],
    token: str,
) -> AskUserQuestionOptionEntry | None:
    if token.isdigit():
        index = int(token) - 1
        if 0 <= index < len(options):
            return options[index]
    lowered = token.casefold()
    return next((option for option in options if option.label.casefold() == lowered), None)
