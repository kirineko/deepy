from __future__ import annotations

import asyncio
import contextlib
import io
import os
import queue
import re
import select
import shutil
import threading
import time
from collections.abc import Callable, Coroutine, Sequence
from concurrent.futures import Future
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from rich.cells import cell_len
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

from deepy import __version__
from deepy.audit import ApprovalDecision, AuditModeState, AuditPolicy, PendingApproval
from deepy.background_tasks import BackgroundTaskManager, BackgroundTaskSnapshot
from deepy.config import (
    PROVIDER_CATALOG,
    Settings,
    UI_THEMES,
    allows_custom_model_for_provider,
    default_base_url_for_provider,
    default_model_for_provider,
    is_supported_model_for_provider,
    is_supported_provider,
    is_valid_thinking_mode_for_provider,
    load_settings,
    provider_info_for,
    ui_theme_from_selection,
    ui_theme_number,
    update_config_input_suggestions_enabled,
    update_config_model_settings,
    update_config_theme,
    update_config_view_mode,
    write_config,
)
from deepy.input_suggestions import (
    InputSuggestion,
    InputSuggestionController,
    generate_input_suggestion,
    is_eligible_for_input_suggestion,
)
from deepy.llm.cache_context import format_cache_hit_rate, format_cache_usage
from deepy.llm.context import estimate_tokens_for_text
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.compaction import ContextCompactionError
from deepy.llm.runner import RunSummary, run_prompt_once
from deepy.mcp import DeepyMcpRuntime, format_mcp_status
from deepy.prompts.init_agents import build_agents_init_prompt
from deepy.prompts.rules import has_agents_instructions
from deepy.sessions import DeepySession, SessionEntry, list_session_entries
from deepy.session_cost import (
    balance_snapshot_to_dict,
    should_track_session_cost,
    supports_session_cost,
)
from deepy.sessions.manager import DeepySessionManager
from deepy.skill_market import (
    install_market_skill,
    list_installed_skills,
    search_market_skills,
    uninstall_market_skill,
    update_market_skill,
)
from deepy.skills import SkillInfo, discover_skills, find_skill, format_skills_for_terminal, read_skill_body
from deepy.status import (
    BalanceStatus,
    build_status_report,
    fetch_deepseek_balance,
    format_compact_status_report,
)
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
from deepy.ui.audit_approval_picker import AUDIT_APPROVAL_APPROVE
from deepy.ui.audit_approval_picker import pick_audit_approval
from deepy.ui.audit_approval_panel import build_approval_panel
from deepy.ui.exit_summary import build_exit_summary_text
from deepy.ui.local_command import (
    LocalCommandInput,
    build_synthetic_shell_transcript_items,
    parse_local_command,
    run_local_command,
    shell_tool_result_json,
)
from deepy.ui.message_view import (
    ToolOutputView,
    format_tool_display_name,
    format_tool_display_label,
    format_tool_call_summary,
    format_tool_progress_summary,
    parse_tool_output,
    render_shell_output_block,
    render_todo_board,
    render_tool_diff_preview,
    should_omit_success_summary,
    tool_status_style,
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
from deepy.ui.slash_commands import build_subagent_slash_prompt
from deepy.ui.slash_commands import is_builtin_slash_command
from deepy.ui.slash_commands import is_subagent_slash_command
from deepy.ui.status_footer import StatusFooter, StatusFooterSegment
from deepy.ui.styles import (
    DARK_PALETTE,
    UiPalette,
    resolve_ui_palette,
    status_style,
)
from deepy.ui.theme_picker import THEME_CHOICES, pick_theme
from deepy.ui.model_picker import (
    pick_model,
    pick_provider,
    pick_reasoning_mode,
    provider_api_key_reconfiguration_message,
    thinking_mode_choices,
)
from deepy.ui.welcome import build_welcome_panel, format_home_relative_path
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
RUNTIME_STATUS_REFRESH_SECONDS = 1.0
RUNTIME_STREAM_STATUS_UPDATE_SECONDS = 0.2


class _AsyncRuntimeWorker:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="deepy-async-runtime", daemon=True)
        self._closed = False
        self._thread.start()
        self._ready.wait()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            pending = [task for task in asyncio.all_tasks(self._loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    def submit(self, coroutine: Coroutine[Any, Any, Any]) -> Future[Any]:
        if self._closed:
            raise RuntimeError("async runtime is closed")
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def run(self, coroutine: Coroutine[Any, Any, Any]) -> Any:
        return self.submit(coroutine).result()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)


@dataclass
class _MainThreadCall:
    callback: Callable[[], Any]
    result: Future[Any]


class _MainThreadCallbackBridge:
    def __init__(self) -> None:
        self._requests: queue.Queue[_MainThreadCall] = queue.Queue()
        self._owner = threading.current_thread()

    def call(self, callback: Callable[[], Any]) -> Any:
        if threading.current_thread() is self._owner:
            return callback()
        result: Future[Any] = Future()
        self._requests.put(_MainThreadCall(callback=callback, result=result))
        return result.result()

    def wait_for_future(self, future: Future[Any]) -> Any:
        while True:
            if future.done():
                return future.result()
            try:
                request = self._requests.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                request.result.set_result(request.callback())
            except BaseException as exc:
                request.result.set_exception(exc)


@dataclass(frozen=True)
class _StartupSnapshot:
    update_pending: bool
    version_update: VersionUpdate | None
    update_reported: bool
    update_notice_pending: bool
    mcp_pending: bool
    mcp_failed: bool


class _StartupState:
    def __init__(self, *, update_pending: bool = False, mcp_pending: bool = False) -> None:
        self._lock = threading.RLock()
        self._update_pending = update_pending
        self._version_update: VersionUpdate | None = None
        self._update_reported = False
        self._update_notice_pending = False
        self._prompt_started = False
        self._mcp_pending = mcp_pending
        self._mcp_failed = False

    def snapshot(self) -> _StartupSnapshot:
        with self._lock:
            return _StartupSnapshot(
                update_pending=self._update_pending,
                version_update=self._version_update,
                update_reported=self._update_reported,
                update_notice_pending=self._update_notice_pending,
                mcp_pending=self._mcp_pending,
                mcp_failed=self._mcp_failed,
            )

    def mark_prompt_started(self) -> None:
        with self._lock:
            self._prompt_started = True
            if self._version_update is not None and not self._update_reported:
                self._update_notice_pending = True

    def mark_welcome_rendered(self, version_update: VersionUpdate | None) -> None:
        if version_update is None:
            return
        with self._lock:
            if self._version_update == version_update:
                self._update_reported = True
                self._update_notice_pending = False

    def mark_update_complete(self, version_update: VersionUpdate | None) -> None:
        with self._lock:
            self._update_pending = False
            self._version_update = version_update
            if version_update is not None and self._prompt_started and not self._update_reported:
                self._update_notice_pending = True

    def mark_update_failed(self) -> None:
        with self._lock:
            self._update_pending = False

    def mark_mcp_complete(self) -> None:
        with self._lock:
            self._mcp_pending = False
            self._mcp_failed = False

    def mark_mcp_failed(self) -> None:
        with self._lock:
            self._mcp_pending = False
            self._mcp_failed = True

    def take_update_notice(self) -> VersionUpdate | None:
        with self._lock:
            if not self._update_notice_pending or self._version_update is None:
                return None
            self._update_notice_pending = False
            self._update_reported = True
            return self._version_update


class _McpStartupHandle:
    def __init__(self, future: Future[Any], startup_state: _StartupState) -> None:
        self._future = future
        self._startup_state = startup_state

    def wait(self) -> None:
        try:
            self._future.result()
        except Exception:
            self._startup_state.mark_mcp_failed()

    def cancel(self) -> None:
        if not self._future.done():
            self._future.cancel()


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
    settings = _ensure_interactive_theme(settings)
    audit_state = AuditModeState(settings.audit.mode)
    audit_policy = AuditPolicy(lambda: audit_state.mode, settings.audit)
    palette = resolve_ui_palette(settings.ui.theme)
    startup_state = _StartupState(
        update_pending=version_update_checker is not None,
        mcp_pending=True,
    )

    loaded_skill_names: list[str] = []
    ctrl_d_exit_pending = False
    input_suggestions = InputSuggestionController(
        enabled=settings.ui.input_suggestions_enabled
    )
    prompt_session = _create_interactive_prompt_session(
        root,
        palette,
        loaded_skill_names,
        input_suggestions=input_suggestions,
        audit_state=audit_state,
    )
    async_runner = _AsyncRuntimeWorker()
    mcp_runtime = _create_mcp_runtime(settings, project_root=root, audit_policy=audit_policy)
    background_tasks = BackgroundTaskManager()
    mcp_startup = _McpStartupHandle(
        async_runner.submit(_connect_mcp_for_startup(mcp_runtime, startup_state)),
        startup_state,
    )
    version_check_thread = _start_background_version_update_check(
        version_update_checker,
        startup_state,
    )
    _settle_startup_version_update_for_welcome(version_check_thread)
    welcome_version_update = startup_state.snapshot().version_update
    output.print(
        build_welcome_panel(
            provider=settings.model.provider,
            model=settings.model.name,
            thinking_enabled=settings.model.thinking_enabled,
            reasoning_effort=settings.model.reasoning_effort,
            thinking_mode=settings.model.reasoning_mode,
            project_root=root,
            skills=discover_skills(root),
            current_version=__version__,
            version_update=welcome_version_update,
            theme=settings.ui.theme,
            resolved_theme=palette.name,
            palette=palette,
        )
    )
    startup_state.mark_welcome_rendered(welcome_version_update)

    try:
        while True:
            try:
                startup_state.mark_prompt_started()
                _flush_startup_notifications(output, startup_state, palette=palette)
                text = prompt_for_input(
                    prompt_session,
                    bottom_toolbar=_build_prompt_toolbar_provider(
                        session_id,
                        project_root=root,
                        settings=settings,
                        mcp_runtime=mcp_runtime,
                        background_tasks=background_tasks,
                        startup_state=startup_state,
                        audit_state=audit_state,
                    ),
                    input_suggestions=input_suggestions,
                )
                input_suggestions.dismiss()
            except EOFError:
                if ctrl_d_exit_pending:
                    _print_exit_summary(output, root, session_id, settings)
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
                    _print_exit_summary(output, root, session_id, settings)
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
                continue

            slash = parse_slash_command(text)
            if slash is not None:
                if is_subagent_slash_command(slash.name):
                    _print_submitted_user_input(output, text, palette=palette)
                    cost_start = _capture_session_cost_start(root, session_id, settings)
                    summary = _run_once_with_status(
                        output,
                        run_once,
                        build_subagent_slash_prompt(slash.name, slash.argument),
                        project_root=root,
                        settings=settings,
                        session_id=session_id,
                        skill_names=list(loaded_skill_names),
                        palette=palette,
                        async_runner=async_runner,
                        mcp_runtime=mcp_runtime,
                        background_tasks=background_tasks,
                        startup_state=startup_state,
                        mcp_startup=mcp_startup,
                        audit_mode=audit_state,
                    )
                    session_id = summary.session_id
                    _record_session_cost_start(root, session_id, cost_start)
                    _print_assistant_output(output, summary.output, palette=palette)
                    _print_usage_footer(output, summary, settings=settings, project_root=root, palette=palette)
                    _prepare_input_suggestion(
                        async_runner,
                        input_suggestions,
                        root,
                        settings,
                        summary,
                    )
                    continue
                if slash.name.startswith("skill:") or not is_builtin_slash_command(slash.name):
                    skill_name = (
                        slash.name.removeprefix("skill:")
                        if slash.name.startswith("skill:")
                        else slash.name
                    )
                    skill = find_skill(root, skill_name)
                    if skill is None:
                        if slash.name.startswith("skill:"):
                            output.print(f"[{palette.error}]Skill not found:[/] {skill_name}")
                            continue
                    else:
                        request = slash.argument or f"Use the {skill.name} skill."
                        _print_submitted_user_input(output, text, palette=palette)
                        cost_start = _capture_session_cost_start(root, session_id, settings)
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
                            background_tasks=background_tasks,
                            startup_state=startup_state,
                            mcp_startup=mcp_startup,
                            audit_mode=audit_state,
                        )
                        session_id = summary.session_id
                        _record_session_cost_start(root, session_id, cost_start)
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
                            cost_start = _capture_session_cost_start(root, session_id, settings)
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
                                background_tasks=background_tasks,
                                startup_state=startup_state,
                                mcp_startup=mcp_startup,
                                audit_mode=audit_state,
                            )
                            session_id = summary.session_id
                            _record_session_cost_start(root, session_id, cost_start)
                        _print_assistant_output(output, summary.output, palette=palette)
                        _print_usage_footer(output, summary, settings=settings, project_root=root, palette=palette)
                        _prepare_input_suggestion(
                            async_runner,
                            input_suggestions,
                            root,
                            settings,
                            summary,
                        )
                        continue
                if slash.name == "init":
                    _print_submitted_user_input(output, text, palette=palette)
                    cost_start = _capture_session_cost_start(root, session_id, settings)
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
                        background_tasks=background_tasks,
                        startup_state=startup_state,
                        mcp_startup=mcp_startup,
                        audit_mode=audit_state,
                    )
                    session_id = summary.session_id
                    _record_session_cost_start(root, session_id, cost_start)
                    _print_assistant_output(output, summary.output, palette=palette)
                    _print_usage_footer(output, summary, settings=settings, project_root=root, palette=palette)
                    _prepare_input_suggestion(
                        async_runner,
                        input_suggestions,
                        root,
                        settings,
                        summary,
                    )
                    continue
                next_session = _handle_slash_command(
                    slash,
                    output,
                    root,
                    session_id,
                    loaded_skill_names,
                    settings=settings,
                    input_func=_prompt_for_background_stop_selection,
                    palette=palette,
                    mcp_runtime=mcp_runtime,
                    background_tasks=background_tasks,
                    startup_state=startup_state,
                )
                if next_session == "__exit__":
                    return 0
                if slash.name in {"theme", "reset", "model", "view"}:
                    settings = load_theme_settings(settings)
                    input_suggestions.set_enabled(settings.ui.input_suggestions_enabled)
                    palette = resolve_ui_palette(settings.ui.theme)
                if slash.name == "input-suggestion":
                    settings = load_settings(settings.path) if settings.path is not None else settings
                    input_suggestions.set_enabled(settings.ui.input_suggestions_enabled)
                if slash.name in {"skills", "theme", "reset", "model", "input-suggestion", "view"}:
                    prompt_session = _create_interactive_prompt_session(
                        root,
                        palette,
                        loaded_skill_names,
                        input_suggestions=input_suggestions,
                        audit_state=audit_state,
                    )
                session_id = next_session
                continue

            _print_submitted_user_input(output, text, palette=palette)
            cost_start = _capture_session_cost_start(root, session_id, settings)
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
                background_tasks=background_tasks,
                startup_state=startup_state,
                mcp_startup=mcp_startup,
                audit_mode=audit_state,
            )
            session_id = summary.session_id
            _record_session_cost_start(root, session_id, cost_start)
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
                cost_start = _capture_session_cost_start(root, session_id, settings)
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
                    background_tasks=background_tasks,
                    startup_state=startup_state,
                    mcp_startup=mcp_startup,
                    audit_mode=audit_state,
                )
                session_id = summary.session_id
                _record_session_cost_start(root, session_id, cost_start)
            _print_assistant_output(output, summary.output, palette=palette)
            _print_usage_footer(output, summary, settings=settings, project_root=root, palette=palette)
            _prepare_input_suggestion(
                async_runner,
                input_suggestions,
                root,
                settings,
                summary,
            )
    finally:
        _cleanup_background_tasks(output, background_tasks, palette=palette)
        mcp_startup.cancel()
        try:
            async_runner.run(mcp_runtime.cleanup())
        finally:
            async_runner.close()

def _create_interactive_prompt_session(
    root: Path,
    palette: UiPalette,
    loaded_skill_names: list[str],
    input_suggestions: InputSuggestionController | None = None,
    audit_state: AuditModeState | None = None,
):
    def cycle_audit_mode() -> None:
        if audit_state is not None:
            audit_state.cycle()

    return create_prompt_session(
        slash_commands=build_slash_commands(
            discover_skills(root),
            loaded_skill_names=loaded_skill_names,
        ),
        palette=palette,
        project_root=root,
        input_suggestions=input_suggestions,
        on_audit_mode_cycle=cycle_audit_mode if audit_state is not None else None,
    )


def _create_mcp_runtime(
    settings: Settings,
    *,
    project_root: Path,
    audit_policy: AuditPolicy,
) -> DeepyMcpRuntime:
    try:
        return DeepyMcpRuntime(settings, project_root=project_root, audit_policy=audit_policy)
    except TypeError as exc:
        if "audit_policy" not in str(exc):
            raise
        return DeepyMcpRuntime(settings, project_root=project_root)


def _prepare_input_suggestion(
    async_runner: Any,
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
    session = DeepySession.open(project_root, summary.session_id)
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
    session = DeepySession.open(project_root, summary.session_id)
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


def _start_background_version_update_check(
    version_update_checker: VersionUpdateChecker | None,
    startup_state: _StartupState,
) -> threading.Thread | None:
    if version_update_checker is None:
        startup_state.mark_update_complete(None)
        return None

    def worker() -> None:
        try:
            startup_state.mark_update_complete(
                _check_startup_version_update(version_update_checker)
            )
        except Exception:
            startup_state.mark_update_failed()

    thread = threading.Thread(target=worker, name="deepy-version-check", daemon=True)
    thread.start()
    return thread


def _settle_startup_version_update_for_welcome(thread: threading.Thread | None) -> None:
    if thread is None:
        return
    thread.join(timeout=0.02)


async def _connect_mcp_for_startup(
    mcp_runtime: DeepyMcpRuntime,
    startup_state: _StartupState,
) -> None:
    try:
        await mcp_runtime.connect()
    except Exception:
        startup_state.mark_mcp_failed()
        return
    startup_state.mark_mcp_complete()


def _print_startup_update_notice(
    console: Console,
    update: VersionUpdate,
    *,
    palette: UiPalette,
) -> None:
    console.print(
        f"[{palette.warning}]Update available:[/] "
        f"{update.current_version} -> {update.latest_version} ({update.install_hint})"
    )


def _flush_startup_notifications(
    console: Console,
    startup_state: _StartupState,
    *,
    palette: UiPalette,
) -> None:
    update = startup_state.take_update_notice()
    if update is not None:
        _print_startup_update_notice(console, update, palette=palette)


def _ensure_interactive_theme(settings: Settings) -> Settings:
    if settings.path is None or settings.ui.theme_configured:
        return settings
    theme = _prompt_theme_choice(settings.ui.theme)
    update_config_theme(settings.path, theme)
    return load_settings(settings.path)


def _prompt_theme_choice(default: str = "dark") -> str:
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
    startup_state = kwargs.pop("startup_state", None)
    mcp_startup = kwargs.pop("mcp_startup", None)
    palette = kwargs.pop("palette", DARK_PALETTE)
    original_emit_event = kwargs.pop("emit_event", None)
    original_should_interrupt = kwargs.pop("should_interrupt", None)
    audit_mode = kwargs.get("audit_mode")
    project_root = kwargs.get("project_root")
    project_root_text = str(project_root) if project_root is not None else None
    settings = kwargs.get("settings")
    footer = _build_status_footer(
        kwargs.get("session_id"),
        project_root=project_root if isinstance(project_root, Path) else None,
        settings=settings if isinstance(settings, Settings) else None,
        mcp_runtime=kwargs.get("mcp_runtime"),
        background_tasks=kwargs.get("background_tasks"),
        startup_state=startup_state if isinstance(startup_state, _StartupState) else None,
        audit_mode=audit_mode,
    )
    renderer: TerminalStreamRenderer | None = None
    started_at = time.monotonic()
    interrupt_requested = threading.Event()
    suspend_interrupt_watcher = threading.Event()
    main_thread_bridge = _MainThreadCallbackBridge()

    def should_interrupt() -> bool:
        if interrupt_requested.is_set():
            return True
        if callable(original_should_interrupt):
            return bool(original_should_interrupt())
        return False

    kwargs["should_interrupt"] = should_interrupt
    has_custom_approval_resolver = kwargs.get("approval_resolver") is not None

    active_palette = palette if isinstance(palette, UiPalette) else DARK_PALETTE
    view_mode = settings.ui.view_mode if isinstance(settings, Settings) else "concise"
    with _status_display(
        console,
        _working_status_text(started_at, palette=active_palette, footer=footer),
        palette=active_palette,
    ) as status:
        renderer = TerminalStreamRenderer(
            console,
            project_root=project_root_text,
            status=status,
            status_started_at=started_at,
            palette=active_palette,
            footer=footer,
            output_lock=getattr(status, "output_lock", None),
            view_mode=view_mode,
        )
        stop_status_refresh = threading.Event()
        status_thread: threading.Thread | None = None
        if getattr(status, "periodic_refresh", True):
            status_thread = threading.Thread(
                target=_refresh_working_status,
                args=(renderer, stop_status_refresh),
                daemon=True,
            )
            status_thread.start()
        if not has_custom_approval_resolver:
            kwargs["approval_resolver"] = _terminal_approval_resolver(
                console,
                palette,
                project_root=project_root,
                status=status,
                stop_status_refresh=stop_status_refresh,
                status_thread_getter=lambda: status_thread,
                suspend_interrupt_watcher=suspend_interrupt_watcher,
                main_thread_bridge=main_thread_bridge,
            )

        try:
            with _esc_interrupt_watcher(
                interrupt_requested,
                suspend_event=suspend_interrupt_watcher,
            ):
                def emit_event(event: DeepyStreamEvent) -> None:
                    renderer(event)
                    if callable(original_emit_event):
                        original_emit_event(event)

                if isinstance(mcp_startup, _McpStartupHandle):
                    mcp_startup.wait()
                coroutine = run_once(prompt, **kwargs, emit_event=emit_event)
                if hasattr(async_runner, "submit") and callable(async_runner.submit):
                    future = async_runner.submit(coroutine)
                    summary = main_thread_bridge.wait_for_future(future)
                elif hasattr(async_runner, "run") and callable(async_runner.run):
                    summary = async_runner.run(coroutine)
                else:
                    summary = asyncio.run(coroutine)
        finally:
            stop_status_refresh.set()
            if status_thread is not None:
                status_thread.join(timeout=0.2)

    renderer.flush()
    return summary


def _terminal_approval_resolver(
    console: Console,
    palette: UiPalette | None,
    *,
    project_root: str | Path | None = None,
    status: object | None = None,
    stop_status_refresh: threading.Event | None = None,
    status_thread_getter: Callable[[], threading.Thread | None] | None = None,
    suspend_interrupt_watcher: threading.Event | None = None,
    main_thread_bridge: _MainThreadCallbackBridge | None = None,
) -> Callable[[list[PendingApproval]], list[ApprovalDecision]]:
    active_palette = palette or DARK_PALETTE

    def resolve(pending: list[PendingApproval]) -> list[ApprovalDecision]:
        decisions: list[ApprovalDecision] = []
        for item in pending:
            def decide(item: PendingApproval = item) -> bool:
                return _collect_terminal_approval_decision(
                    item,
                    console=console,
                    palette=active_palette,
                    project_root=project_root,
                    status=status,
                    stop_status_refresh=stop_status_refresh,
                    status_thread_getter=status_thread_getter,
                    suspend_interrupt_watcher=suspend_interrupt_watcher,
                )

            approved = main_thread_bridge.call(decide) if main_thread_bridge is not None else decide()
            decisions.append(
                ApprovalDecision(
                    outcome="approve" if approved else "reject",
                    rejection_message=None
                    if approved
                    else "Tool execution was rejected by the user audit approval decision.",
                )
            )
        return decisions

    return resolve


def _collect_terminal_approval_decision(
    item: PendingApproval,
    *,
    console: Console,
    palette: UiPalette,
    project_root: str | Path | None = None,
    status: object | None,
    stop_status_refresh: threading.Event | None,
    status_thread_getter: Callable[[], threading.Thread | None] | None,
    suspend_interrupt_watcher: threading.Event | None,
) -> bool:
    if suspend_interrupt_watcher is not None:
        suspend_interrupt_watcher.set()
    try:
        _prepare_terminal_approval_prompt(
            status=status,
            stop_status_refresh=stop_status_refresh,
            status_thread_getter=status_thread_getter,
        )
        _, can_expand = _approval_panel_state(
            item,
            palette=palette,
            project_root=project_root,
            expanded=False,
            width=console.width,
        )
        choice = pick_audit_approval(
            can_toggle_preview=can_expand,
            expanded=False,
            panel_text_factory=lambda expanded: _approval_panel_ansi(
                item,
                palette=palette,
                project_root=project_root,
                expanded=expanded,
                width=console.width,
            ),
        )
        return choice == AUDIT_APPROVAL_APPROVE
    finally:
        if suspend_interrupt_watcher is not None:
            suspend_interrupt_watcher.clear()


def _prepare_terminal_approval_prompt(
    *,
    status: object | None,
    stop_status_refresh: threading.Event | None,
    status_thread_getter: Callable[[], threading.Thread | None] | None,
) -> None:
    if stop_status_refresh is not None:
        stop_status_refresh.set()
    if status_thread_getter is not None:
        thread = status_thread_getter()
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.2)
    clear_for_output = getattr(status, "clear_for_output", None)
    if callable(clear_for_output):
        clear_for_output()
        return
    clear = getattr(status, "clear", None)
    if callable(clear):
        clear()


def _approval_panel(
    item: PendingApproval,
    *,
    palette: UiPalette,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
) -> Panel:
    panel, _ = _approval_panel_state(
        item,
        palette=palette,
        project_root=project_root,
        expanded=expanded,
        width=width,
    )
    return panel


def _approval_panel_ansi(
    item: PendingApproval,
    *,
    palette: UiPalette,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
    color_system: Literal["auto", "standard", "256", "truecolor", "windows"] | None = "truecolor",
) -> str:
    buffer = io.StringIO()
    render_console = Console(
        file=buffer,
        force_terminal=True,
        color_system=color_system,
        width=width,
    )
    render_console.print(
        _approval_panel(
            item,
            palette=palette,
            project_root=project_root,
            expanded=expanded,
            width=width,
        )
    )
    return buffer.getvalue().rstrip("\n")


def _approval_panel_state(
    item: PendingApproval,
    *,
    palette: UiPalette,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
) -> tuple[Panel, bool]:
    return build_approval_panel(
        item,
        palette=palette,
        project_root=project_root,
        expanded=expanded,
        width=width,
    )


def _append_approval_field(
    text: Text,
    label: str,
    value: object,
    *,
    palette: UiPalette,
) -> None:
    if text.plain:
        text.append("\n")
    text.append(f"{label}: ", style=f"bold {palette.muted}")
    text.append(str(value))


def _approval_arguments_text(item: PendingApproval, *, palette: UiPalette) -> Text:
    arguments = item.arguments.strip()
    if not arguments:
        return Text()
    try:
        parsed = json_utils.loads(arguments)
    except json_utils.JSONDecodeError:
        return _approval_block_text("arguments", arguments, palette=palette)
    if not isinstance(parsed, dict):
        return _approval_block_text("arguments", json_utils.dumps_pretty(parsed), palette=palette)

    text = Text()
    displayed: set[str] = set()
    for key in ("command", "path", "url", "format"):
        value = parsed.get(key)
        if isinstance(value, str) and value:
            _append_approval_field(text, f"arguments.{key}", value, palette=palette)
            displayed.add(key)
    urls = parsed.get("urls")
    if isinstance(urls, list) and urls:
        _append_approval_field(text, "arguments.urls", ", ".join(str(url) for url in urls), palette=palette)
        displayed.add("urls")
    content = parsed.get("content")
    if isinstance(content, str):
        if text.plain:
            text.append("\n")
        text.append(_approval_block_text("arguments.content preview", content, palette=palette))
        displayed.add("content")

    remaining = {key: value for key, value in parsed.items() if key not in displayed}
    if remaining:
        if text.plain:
            text.append("\n")
        text.append(
            _approval_block_text(
                "arguments.other",
                json_utils.dumps_pretty(remaining),
                palette=palette,
            )
        )
    return text


def _approval_block_text(
    label: str,
    value: str,
    *,
    palette: UiPalette,
    max_lines: int = 18,
    max_line_chars: int = 140,
) -> Text:
    text = Text()
    text.append(f"{label}:\n", style=f"bold {palette.muted}")
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    visible = lines[:max_lines]
    for line in visible:
        text.append("  ", style=palette.muted)
        text.append(_truncate_approval_line(line, max_chars=max_line_chars))
        text.append("\n")
    omitted = len(lines) - len(visible)
    if omitted > 0:
        text.append(f"  ... truncated {omitted} lines\n", style=palette.muted)
    if text.plain.endswith("\n"):
        text.rstrip()
    return text


def _truncate_approval_line(value: str, *, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1] + "…"


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

    _print_submitted_user_input(console, command_input.raw_text, palette=palette)
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
    shell_output = render_shell_output_block(tool_output, palette=palette, width=console.width)
    if shell_output:
        console.print(shell_output)

    session = (
        DeepySession.open(project_root, current_session_id)
        if current_session_id
        else DeepySession.create(project_root)
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


def _format_background_tasks_for_terminal(
    background_tasks: BackgroundTaskManager | None,
    *,
    active_only: bool = False,
) -> str:
    if background_tasks is None:
        return "Background task management is not available in this UI."
    tasks = background_tasks.list(active_only=active_only)
    if not tasks:
        return "No running background tasks." if active_only else "No background tasks."
    return "\n".join(_format_background_task_for_terminal(task) for task in tasks)


def _format_background_task_for_terminal(task: BackgroundTaskSnapshot) -> str:
    pid = f" pid={task.pid}" if task.pid is not None else ""
    exit_code = f" exit={task.exit_code}" if task.exit_code is not None else ""
    stopped = " stop_requested" if task.stop_requested else ""
    return f"{task.id}\t{task.status}{pid}{exit_code}{stopped}\t{task.command}"


def _stop_background_tasks_for_terminal(
    background_tasks: BackgroundTaskManager | None,
    *,
    selection: str = "",
    input_func: InputFunc | None = None,
    console: Console | None = None,
) -> str:
    if background_tasks is None:
        return "Background task management is not available in this UI."
    running_tasks = background_tasks.list(active_only=True)
    if not running_tasks:
        return "No running background tasks."
    resolved_selection = _resolve_background_stop_selection(
        running_tasks,
        selection=selection,
        input_func=input_func,
        console=console,
    )
    if resolved_selection is None:
        return "Stop canceled."
    if resolved_selection == "__invalid__":
        return "Invalid background task selection."
    if resolved_selection == "all":
        return _stop_all_background_tasks_for_terminal(background_tasks)
    snapshot = background_tasks.stop(resolved_selection, force_after_grace=True)
    if snapshot is None:
        return f"Background task not found: {resolved_selection}"
    return f"Stop requested for background task {snapshot.id}."


def _resolve_background_stop_selection(
    running_tasks: Sequence[BackgroundTaskSnapshot],
    *,
    selection: str = "",
    input_func: InputFunc | None = None,
    console: Console | None = None,
) -> str | None:
    selected = selection.strip()
    if selected:
        return _parse_background_stop_selection(running_tasks, selected)
    if input_func is None:
        return "all"
    choices = ["Running background tasks:"]
    choices.extend(
        f"{index}. {_format_background_task_for_terminal(task)}"
        for index, task in enumerate(running_tasks, start=1)
    )
    choices.append(f"{len(running_tasks) + 1}. all\tStop all running background tasks")
    choices.append(f"{len(running_tasks) + 2}. cancel\tReturn without stopping tasks")
    if console is not None:
        console.print("\n".join(choices))
    prompt = "Stop background task number, id, or Esc to cancel"
    response = input_func(prompt)
    return _parse_background_stop_selection(running_tasks, response.strip())


def _parse_background_stop_selection(
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


def _stop_all_background_tasks_for_terminal(background_tasks: BackgroundTaskManager) -> str:
    summary = background_tasks.stop_all(force_after_grace=True)
    count = len(summary.stopped)
    task_label = "task" if count == 1 else "tasks"
    return f"Stop requested for {count} background {task_label}."


def _prompt_for_background_stop_selection(prompt: str) -> str:
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        event.app.exit(result="")

    session: PromptSession[str] = PromptSession(key_bindings=bindings)
    try:
        return session.prompt(f"{prompt}: ").strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def _cleanup_background_tasks(
    console: Console,
    background_tasks: BackgroundTaskManager,
    *,
    palette: UiPalette,
) -> None:
    running = background_tasks.running_count()
    if running == 0:
        return
    summary = background_tasks.stop_all(force_after_grace=True)
    count = len(summary.stopped)
    task_label = "task" if count == 1 else "tasks"
    console.print(f"[{palette.muted}]Stopped {count} background {task_label}.[/]")


@contextlib.contextmanager
def _esc_interrupt_watcher(
    interrupt_requested: threading.Event,
    *,
    suspend_event: threading.Event | None = None,
):
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
        args=(interrupt_requested, stop_event, suspend_event),
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
    suspend_event: threading.Event | None = None,
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
            if suspend_event is not None and suspend_event.is_set():
                time.sleep(0.05)
                continue
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
    suspend_event: threading.Event | None = None,
) -> None:
    if msvcrt is None:
        return
    kbhit = getattr(msvcrt, "kbhit", None)
    getwch = getattr(msvcrt, "getwch", None)
    if not callable(kbhit) or not callable(getwch):
        return
    while not stop_event.is_set() and not interrupt_requested.is_set():
        if suspend_event is not None and suspend_event.is_set():
            time.sleep(0.05)
            continue
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
        output_lock: threading.RLock | None = None,
        view_mode: str = "concise",
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
        self.reasoning_updated_at = 0.0
        self.view_mode = view_mode if view_mode in {"concise", "full"} else "concise"
        self.stream_tokens = 0
        self.stream_status_updated_at = 0.0
        self.activity_state = ""
        self.output_lock = output_lock

    def __call__(self, event: DeepyStreamEvent) -> None:
        if self.output_lock is None:
            self._record_stream_progress(event)
            if self._stream_event_writes_terminal(event):
                self._clear_status_for_output()
            self._update_status_for_silent_generation(event)
            _print_stream_event(
                self.console,
                event,
                project_root=self.project_root,
                pending_tool_calls=self.pending_tool_calls,
                reasoning_sink=self,
                palette=self.palette,
            )
            return
        with self.output_lock:
            self._record_stream_progress(event)
            if self._stream_event_writes_terminal(event):
                self._clear_status_for_output()
            self._update_status_for_silent_generation(event)
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
        self.activity_state = "Thinking"
        if self.view_mode == "concise":
            if self.status is not None:
                self.update_status(self._runtime_status_detail())
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
        self.reasoning_updated_at = time.monotonic()
        self.console.print(Text(text, style=self.palette.muted), end="")
        if self.status is not None:
            self.update_status(self._runtime_status_detail())

    def set_tool_status(self, tool_name: str) -> None:
        self.activity_state = _runtime_tool_activity_name(tool_name)
        if self.status is not None and self.activity_state:
            self.update_status(self._runtime_status_detail())

    def update_status(self, detail: str | None = None) -> None:
        if detail is not None:
            self.status_detail = detail
        if self.status is not None and not self._status_output_is_blocked():
            if (
                self._status_detail_has_stream_tokens()
                and getattr(self.status, "inline_output_flow", False)
                and getattr(self.status, "active", False)
            ):
                now = time.monotonic()
                if now - self.stream_status_updated_at < RUNTIME_STREAM_STATUS_UPDATE_SECONDS:
                    return
                self.stream_status_updated_at = now
            self.status.update(
                _working_status_text(
                    self.status_started_at,
                    self.status_detail,
                    palette=self.palette,
                    footer=self.footer,
                )
            )

    def refresh_status(self) -> None:
        if self.output_lock is not None:
            with self.output_lock:
                self.update_status()
            return
        self.update_status()

    def _clear_status_for_output(self) -> None:
        clear_for_output = getattr(self.status, "clear_for_output", None)
        if callable(clear_for_output):
            clear_for_output()

    def _status_output_is_blocked(self) -> bool:
        if not (self.reasoning_buffer and getattr(self.status, "inline_output_flow", False)):
            return False
        if time.monotonic() - self.reasoning_updated_at < RUNTIME_STATUS_REFRESH_SECONDS:
            return True
        self._flush_unlocked()
        return False

    def _update_status_for_silent_generation(self, event: DeepyStreamEvent) -> None:
        detail = _silent_generation_status_detail(event)
        if self.status is None or detail is None:
            return
        if detail == "":
            if event.kind in {"text_delta", "message"}:
                self.activity_state = "Responding"
            detail = self._runtime_status_detail()
        if self.reasoning_buffer:
            self._flush_unlocked()
        if self.status_detail == detail and getattr(self.status, "active", False):
            return
        self.update_status(detail)

    def _record_stream_progress(self, event: DeepyStreamEvent) -> None:
        if event.kind not in {"reasoning_delta", "text_delta", "raw_response"} or not event.text:
            return
        self.stream_tokens += estimate_tokens_for_text(event.text)

    def _stream_status_detail(self) -> str | None:
        if self.stream_tokens <= 0:
            return None
        return f"↓ {_format_stream_token_count_short(self.stream_tokens)} tokens"

    def _runtime_status_detail(self) -> str:
        parts: list[str] = []
        stream_detail = self._stream_status_detail()
        if stream_detail:
            parts.append(stream_detail)
        if self.activity_state:
            parts.append(self.activity_state)
        return _STATUS_SEPARATOR.join(parts)

    def _status_detail_has_stream_tokens(self) -> bool:
        return self.status_detail == "↓ " or self.status_detail.startswith("↓ ")

    def flush(self) -> None:
        if self.output_lock is not None:
            with self.output_lock:
                self._flush_unlocked()
            return
        self._flush_unlocked()

    def _flush_unlocked(self) -> None:
        if self.reasoning_buffer:
            self.console.print()
        self.reasoning_started = False
        self.reasoning_buffer = ""

    def _stream_event_writes_terminal(self, event: DeepyStreamEvent) -> bool:
        if event.kind == "reasoning_delta" and self.view_mode == "concise":
            return False
        return _stream_event_writes_terminal(event)

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
    background_tasks: BackgroundTaskManager | None = None,
    startup_state: _StartupState | None = None,
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
        console.print("/explore    Delegate investigation to the explore subagent")
        console.print("/reviewer   Delegate review to the reviewer subagent")
        console.print("/tester     Delegate verification to the tester subagent")
        console.print("/NAME       Invoke a skill by name")
        console.print("/init      Create or update project AGENTS.md")
        console.print("/mcp       Show MCP server status and tools")
        console.print("/ps        Show background tasks")
        console.print("/stop      Choose background tasks to stop")
        console.print("/model      Select model and thinking strength")
        console.print("/view \\[toggle|concise|full] Hide or show reasoning transcript text")
        console.print("/input-suggestion Toggle input suggestions")
        console.print("/status     Show status, usage, and DeepSeek balance")
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
            _resume_session(console, project_root, session_id, palette=palette, settings=settings)
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
        _resume_session(console, project_root, selected.id, palette=palette, settings=settings)
        return selected.id
    if command.name == "sessions":
        entries = list_session_entries(project_root)
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        for entry in entries:
            console.print(
                f"{entry.id}\tupdated={entry.updated_at}\thistory_estimate={entry.active_tokens}\t"
                f"{format_usage_line(entry.usage)}\tcache={_format_session_cache_for_list(entry)}"
            )
        return current_session_id
    if command.name == "status":
        balance = (
            fetch_deepseek_balance(settings)
            if supports_session_cost(settings)
            else BalanceStatus(unavailable_reason="unsupported provider")
        )
        console.print(
            format_compact_status_report(
                build_status_report(
                    project_root,
                    settings,
                    current_session_id=current_session_id,
                    balance=balance,
                )
            )
        )
        return current_session_id
    if command.name == "mcp":
        startup_snapshot = startup_state.snapshot() if startup_state is not None else None
        if startup_snapshot is not None and startup_snapshot.mcp_pending:
            console.print("MCP: connecting.")
            return current_session_id
        statuses = mcp_runtime.statuses if mcp_runtime is not None else []
        if startup_snapshot is not None and startup_snapshot.mcp_failed and not statuses:
            console.print("MCP: startup failed.")
            return current_session_id
        console.print(format_mcp_status(statuses))
        return current_session_id
    if command.name == "ps":
        console.print(_format_background_tasks_for_terminal(background_tasks, active_only=False))
        return current_session_id
    if command.name == "stop":
        console.print(
            _stop_background_tasks_for_terminal(
                background_tasks,
                selection=command.argument,
                input_func=input_func,
                console=console,
            )
        )
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
    if command.name == "view":
        return _handle_view_command(command, console, current_session_id, settings, palette)
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
    session = DeepySession.open(project_root, current_session_id)
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
        console.print(f"[{palette.error}]Usage:[/] /theme dark|light")
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
    if action == "provider" and len(parts) == 2:
        provider = parts[1].lower()
        if not is_supported_provider(provider):
            console.print(f"[{palette.error}]Invalid provider:[/] {provider}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            provider=provider,
        )
    if action == "set" and len(parts) in {2, 3}:
        model = parts[1]
        provider = "deepseek"
        if not is_supported_model_for_provider(model, provider):
            console.print(f"[{palette.error}]Invalid model:[/] {model}")
            _print_model_usage(console, palette)
            return current_session_id
        reasoning_mode = parts[2] if len(parts) == 3 else None
        if reasoning_mode is not None and not is_valid_thinking_mode_for_provider(reasoning_mode, provider):
            console.print(f"[{palette.error}]Invalid thinking mode:[/] {reasoning_mode}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            provider=provider,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    if action == "set" and len(parts) == 4:
        provider = parts[1].lower()
        model = parts[2]
        reasoning_mode = parts[3].lower()
        if not is_supported_provider(provider):
            console.print(f"[{palette.error}]Invalid provider:[/] {provider}")
            _print_model_usage(console, palette)
            return current_session_id
        if not is_supported_model_for_provider(model, provider):
            console.print(f"[{palette.error}]Invalid model:[/] {model}")
            _print_model_usage(console, palette)
            return current_session_id
        if not is_valid_thinking_mode_for_provider(reasoning_mode, provider):
            console.print(f"[{palette.error}]Invalid thinking mode:[/] {reasoning_mode}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            provider=provider,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    if action in {"reasoning", "thinking"} and len(parts) == 2:
        reasoning_mode = parts[1]
        provider = settings.model.provider
        if not is_valid_thinking_mode_for_provider(reasoning_mode, provider):
            console.print(f"[{palette.error}]Invalid thinking mode:[/] {reasoning_mode}")
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


def _handle_view_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    argument = command.argument.strip().lower()
    current = settings.ui.view_mode
    if not argument or argument == "toggle":
        selected = "full" if current == "concise" else "concise"
    elif argument in {"concise", "full"}:
        selected = argument
    else:
        console.print(f"[{palette.error}]Usage:[/] /view \\[toggle|concise|full]")
        return current_session_id
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist view mode: config path is unknown.[/]")
        return current_session_id
    update_config_view_mode(settings.path, selected)
    console.print(_format_view_mode_confirmation(selected))
    return current_session_id


def _format_view_mode_confirmation(view_mode: str) -> str:
    reasoning_state = "reasoning shown" if view_mode == "full" else "reasoning hidden"
    return f"View: {view_mode} · {reasoning_state}"


def _handle_interactive_model_selection(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    console.print(
        f"Current provider: {settings.model.provider} · model: {settings.model.name} · "
        f"thinking: {settings.model.reasoning_mode}"
    )
    selected_provider = _prompt_for_provider_selection(
        settings.model.provider,
        console=console,
        input_func=input_func,
    )
    if selected_provider is None:
        console.print("Model unchanged.")
        return current_session_id
    selected_model = _prompt_for_model_selection(
        settings.model.name if settings.model.provider == selected_provider else default_model_for_provider(selected_provider),
        provider=selected_provider,
        console=console,
        input_func=input_func,
    )
    if selected_model is None:
        console.print("Model unchanged.")
        return current_session_id
    selected_reasoning = _prompt_for_reasoning_mode_selection(
        settings.model.reasoning_mode,
        provider=selected_provider,
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
        provider=selected_provider,
        model=selected_model,
        reasoning_mode=selected_reasoning,
    )


def _save_model_settings(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    *,
    provider: str | None = None,
    model: str | None = None,
    reasoning_mode: str | None = None,
) -> str | None:
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist model settings: config path is unknown.[/]")
        return current_session_id
    try:
        update_config_model_settings(
            settings.path,
            provider=provider,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    except ValueError as exc:
        console.print(f"[{palette.error}]{exc}[/]")
        return current_session_id
    saved_settings = load_settings(settings.path)
    console.print(
        f"Saved provider: {saved_settings.model.provider} · "
        f"model: {saved_settings.model.name} · "
        f"thinking: {saved_settings.model.reasoning_mode}"
    )
    if saved_settings.model.provider != settings.model.provider:
        console.print(provider_api_key_reconfiguration_message(saved_settings.model.provider))
    return current_session_id


def _print_model_choices(console: Console) -> None:
    console.print("Available providers and models:")
    for provider in PROVIDER_CATALOG:
        console.print(f"{provider.id} - {provider.description}")
        for index, model in enumerate(provider.models, 1):
            console.print(f"  {index}. {model.name} - {model.description}")
        modes = ", ".join(provider.thinking_modes)
        console.print(f"  thinking: {modes}")


def _print_model_usage(console: Console, palette: UiPalette) -> None:
    console.print(
        f"[{palette.error}]Usage:[/] /model | /model list | "
        "/model set deepseek-v4-pro|deepseek-v4-flash [none|high|max] | "
        "/model set openrouter xiaomi/mimo-v2.5-pro none|minimal|low|medium|high|xhigh | "
        "/model set xiaomi mimo-v2.5-pro enabled|disabled | "
        "/model provider deepseek|openrouter|xiaomi | "
        "/model thinking <mode>"
    )


def _prompt_for_provider_selection(
    default: str,
    *,
    console: Console,
    input_func: InputFunc | None = None,
) -> str | None:
    if input_func is None:
        return pick_provider(default)
    _print_provider_choices(console)
    value = input_func("Provider number or name").strip()
    if not value:
        return None
    return _provider_from_selection(value)


def _prompt_for_model_selection(
    default: str,
    *,
    provider: str,
    console: Console,
    input_func: InputFunc | None = None,
    allow_custom_model: bool = False,
) -> str | None:
    if input_func is None:
        return pick_model(default, provider=provider)
    _print_provider_model_choices(console, provider)
    if allow_custom_model and allows_custom_model_for_provider(provider):
        console.print("Or paste any model name copied from the OpenRouter models page.")
    value = input_func("Model number or name").strip()
    if not value:
        return None
    return _model_from_selection(value, provider=provider, allow_custom_model=allow_custom_model)


def _prompt_for_reasoning_mode_selection(
    default: str,
    *,
    provider: str,
    console: Console,
    input_func: InputFunc | None = None,
    setup_flow: bool = False,
) -> str | None:
    if input_func is None:
        return pick_reasoning_mode(default, provider=provider)
    if setup_flow and provider == "openrouter":
        return _prompt_for_openrouter_reasoning_setup(default, console=console, input_func=input_func)
    _print_reasoning_choices(console, provider)
    value = input_func("Thinking number or name").strip()
    if not value:
        return None
    return _reasoning_mode_from_selection(value, provider=provider)


def _prompt_for_openrouter_reasoning_setup(
    default: str,
    *,
    console: Console,
    input_func: InputFunc,
) -> str | None:
    current_enabled = default not in {"none", "disabled"}
    console.print("Thinking:")
    console.print("1. enabled - Reasoning enabled")
    console.print("2. disabled - Reasoning disabled")
    state_value = input_func("Thinking number or name").strip()
    if not state_value:
        return None
    state = _openrouter_thinking_state_from_selection(
        state_value,
        default="enabled" if current_enabled else "disabled",
    )
    if state == "disabled":
        return "none"
    console.print("Reasoning effort:")
    console.print("1. default - Use the model default reasoning strength")
    for index, effort in enumerate(("xhigh", "high", "medium", "low", "minimal"), 2):
        console.print(f"{index}. {effort}")
    effort_value = input_func("Reasoning effort number or name").strip()
    if not effort_value:
        return "enabled"
    return _openrouter_effort_from_selection(effort_value, default=default)


def _openrouter_thinking_state_from_selection(value: str, *, default: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"1", "enabled", "enable", "on", "true", "yes"}:
        return "enabled"
    if normalized in {"2", "disabled", "disable", "off", "false", "no", "none"}:
        return "disabled"
    return default


def _openrouter_effort_from_selection(value: str, *, default: str) -> str:
    normalized = value.strip().lower()
    by_number = {
        "1": "enabled",
        "2": "xhigh",
        "3": "high",
        "4": "medium",
        "5": "low",
        "6": "minimal",
    }
    if normalized in by_number:
        return by_number[normalized]
    if normalized in {"default", "enabled"}:
        return "enabled"
    if normalized in {"xhigh", "high", "medium", "low", "minimal"}:
        return normalized
    return default if default in {"enabled", "xhigh", "high", "medium", "low", "minimal"} else "enabled"


def _provider_from_selection(value: str) -> str | None:
    normalized = value.strip().lower()
    by_number = {str(index): provider.id for index, provider in enumerate(PROVIDER_CATALOG, 1)}
    if normalized in by_number:
        return by_number[normalized]
    return normalized if is_supported_provider(normalized) else None


def _model_from_selection(value: str, *, provider: str, allow_custom_model: bool = False) -> str | None:
    normalized = value.strip()
    by_number = {str(index): model.name for index, model in enumerate(provider_info_for(provider).models, 1)}
    if normalized in by_number:
        return by_number[normalized]
    if allow_custom_model and allows_custom_model_for_provider(provider) and normalized:
        return normalized
    return normalized if is_supported_model_for_provider(normalized, provider) else None


def _reasoning_mode_from_selection(value: str, *, provider: str) -> str | None:
    normalized = value.strip().lower()
    choices = thinking_mode_choices(provider)
    by_number = {str(index): mode for index, (mode, _label) in enumerate(choices, 1)}
    if normalized in by_number:
        return by_number[normalized]
    return normalized if is_valid_thinking_mode_for_provider(normalized, provider) else None


def _print_provider_choices(console: Console) -> None:
    console.print("Providers:")
    for index, provider in enumerate(PROVIDER_CATALOG, 1):
        console.print(f"{index}. {provider.id} - {provider.description}")


def _print_provider_model_choices(console: Console, provider: str) -> None:
    console.print(f"Models for {provider}:")
    for index, model in enumerate(provider_info_for(provider).models, 1):
        console.print(f"{index}. {model.name} - {model.description}")


def _print_reasoning_choices(console: Console, provider: str = "deepseek") -> None:
    console.print("Thinking:")
    for index, (value, label) in enumerate(thinking_mode_choices(provider), 1):
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
    return {"1": "dark", "2": "light"}.get(normalized)


def _handle_reset_command(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot reset config: config path is unknown.[/]")
        return current_session_id
    previous_text = settings.path.read_text(encoding="utf-8") if settings.path.exists() else None
    if settings.path.exists():
        settings.path.unlink()
        console.print(f"Removed {settings.path}")
    else:
        console.print(f"No existing config at {settings.path}")
    console.print("Starting Deepy configuration setup...")
    try:
        _run_interactive_config_setup(settings.path, previous=settings, console=console)
    except (KeyboardInterrupt, EOFError, StopIteration):
        _restore_config_after_failed_setup(settings.path, previous_text)
        console.print(f"[{palette.warning}]{_setup_cancelled_message(previous_text)}[/]")
        return current_session_id
    console.print(f"Wrote {settings.path}")
    return current_session_id


def _setup_cancelled_message(previous_text: str | None) -> str:
    if previous_text is None:
        return "Configuration setup cancelled. No config was written."
    return "Configuration setup cancelled. Existing config was left unchanged."


def _restore_config_after_failed_setup(config_path: Path, previous_text: str | None) -> None:
    if previous_text is None:
        try:
            config_path.unlink()
        except FileNotFoundError:
            pass
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(previous_text, encoding="utf-8")
    try:
        config_path.chmod(0o600)
    except OSError:
        pass


def _run_interactive_config_setup(
    config_path: Path,
    *,
    previous: Settings,
    console: Console,
) -> None:
    provider = _prompt_for_provider_selection(
        previous.model.provider,
        console=console,
        input_func=lambda label: _prompt_config_value(label, default=""),
    ) or previous.model.provider
    provider_info = provider_info_for(provider)
    console.print(f"Provider: {provider}")
    if provider_info.api_key_url:
        console.print(f"Create an API key at {provider_info.api_key_url}")
    api_key = _prompt_config_value("API key", default="", is_password=True)
    model_default = (
        previous.model.name
        if previous.model.provider == provider and is_supported_model_for_provider(previous.model.name, provider)
        else default_model_for_provider(provider)
    )
    model = _prompt_for_model_selection(
        model_default,
        provider=provider,
        console=console,
        input_func=lambda label: _prompt_config_value(label, default=""),
        allow_custom_model=True,
    ) or model_default
    base_default = (
        previous.model.base_url
        if previous.model.provider == provider
        else default_base_url_for_provider(provider)
    )
    base_url = _prompt_config_value("Base URL", default=base_default)
    thinking_default = (
        previous.model.reasoning_mode
        if previous.model.provider == provider and is_valid_thinking_mode_for_provider(previous.model.reasoning_mode, provider)
        else provider_info_for(provider).default_thinking_mode
    )
    thinking_mode = _prompt_for_reasoning_mode_selection(
        thinking_default,
        provider=provider,
        console=console,
        input_func=lambda label: _prompt_config_value(label, default=""),
        setup_flow=True,
    ) or thinking_default
    theme = _prompt_theme_config_value(default=previous.ui.theme, console=console)
    write_config(
        config_path,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        thinking_mode=thinking_mode,
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
    settings: Settings | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    console.print(Text.assemble(("Resuming session ", palette.muted), (session_id, palette.info)))
    _print_session_history(console, project_root, session_id, palette=palette, settings=settings)


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
    settings: Settings | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    items = _load_session_items(project_root, session_id)
    if not items:
        console.print(f"[{palette.muted}]No visible history for this session.[/]")
        return

    console.print(Text("History", style=f"bold {palette.muted}"))
    renderer = TerminalStreamRenderer(
        console,
        project_root=str(project_root),
        palette=palette,
        view_mode=settings.ui.view_mode if settings is not None else "concise",
    )
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
        return asyncio.run(DeepySession.open(project_root, session_id).get_items())
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
        _record_session_cost_end(project_root, session_id, settings)
        session_entry = next(
            (entry for entry in list_session_entries(project_root) if entry.id == session_id),
            None,
        )
        try:
            messages = asyncio.run(DeepySession.open(project_root, session_id).get_items())
        except Exception:
            messages = []
    console.print(
        build_exit_summary_text(
            session=session_entry,
            messages=messages,
            model=settings.model.name,
            session_id=session_id,
            session_cost_unsupported=not supports_session_cost(settings),
        )
    )


def _capture_session_cost_start(
    project_root: Path,
    session_id: str | None,
    settings: Settings,
) -> dict[str, Any] | None:
    if not should_track_session_cost(settings):
        return None
    if session_id and _session_cost_has_start(project_root, session_id):
        return None
    return balance_snapshot_to_dict(
        fetch_deepseek_balance(settings),
        captured_at_ms=_now_ms(),
    )


def _record_session_cost_start(
    project_root: Path,
    session_id: str | None,
    snapshot: dict[str, Any] | None,
) -> None:
    if not session_id or snapshot is None:
        return
    try:
        DeepySession.open(project_root, session_id).record_session_cost_start(snapshot)
    except Exception:
        return


def _record_session_cost_end(project_root: Path, session_id: str, settings: Settings) -> None:
    if not should_track_session_cost(settings) or not _session_cost_has_start(project_root, session_id):
        return
    snapshot = balance_snapshot_to_dict(
        fetch_deepseek_balance(settings),
        captured_at_ms=_now_ms(),
    )
    try:
        DeepySession.open(project_root, session_id).record_session_cost_end(snapshot)
    except Exception:
        return


def _session_cost_has_start(project_root: Path, session_id: str) -> bool:
    return any(
        entry.id == session_id
        and isinstance(entry.session_cost, dict)
        and isinstance(entry.session_cost.get("start"), dict)
        for entry in list_session_entries(project_root)
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


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
    background_tasks: BackgroundTaskManager | None = None,
    startup_state: _StartupState | None = None,
    audit_mode: AuditModeState | None = None,
) -> str:
    return _build_status_footer(
        session_id,
        project_root=project_root,
        settings=settings,
        mcp_runtime=mcp_runtime,
        background_tasks=background_tasks,
        startup_state=startup_state,
        audit_mode=audit_mode,
    ).plain


def _build_prompt_toolbar_provider(
    session_id: str | None,
    *,
    project_root: Path,
    settings: Settings,
    mcp_runtime: DeepyMcpRuntime,
    background_tasks: BackgroundTaskManager,
    startup_state: _StartupState,
    audit_state: AuditModeState | None = None,
) -> Callable[[], object]:
    captured_session_id = session_id
    captured_settings = settings

    def toolbar() -> object:
        return build_prompt_toolbar(
            _build_status_footer(
                captured_session_id,
                project_root=project_root,
                settings=captured_settings,
                mcp_runtime=mcp_runtime,
                background_tasks=background_tasks,
                startup_state=startup_state,
                audit_mode=audit_state,
            )
        )

    return toolbar


def _build_status_footer(
    session_id: str | None,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
    background_tasks: BackgroundTaskManager | None = None,
    startup_state: _StartupState | None = None,
    active_work: str | None = None,
    audit_mode: AuditModeState | str | None = None,
) -> StatusFooter:
    if settings is None:
        return StatusFooter(())

    segments = [
        StatusFooterSegment(f"provider {settings.model.provider}", "identity"),
        StatusFooterSegment(
            f"model {settings.model.name}[{settings.model.reasoning_mode}]",
            "identity",
        ),
        StatusFooterSegment(f"audit {_audit_mode_label(audit_mode, settings)}", "metadata"),
    ]
    if project_root is not None:
        segments.append(StatusFooterSegment(f"cwd {format_home_relative_path(project_root)}", "metadata"))
        if has_agents_instructions(project_root):
            segments.append(StatusFooterSegment("[AGENTS.md]", "loaded"))
        if mcp_runtime is not None and mcp_runtime.active_servers:
            segments.append(StatusFooterSegment(f"mcp {len(mcp_runtime.active_servers)}", "loaded"))
        elif startup_state is not None:
            startup_snapshot = startup_state.snapshot()
            if startup_snapshot.mcp_pending:
                segments.append(StatusFooterSegment("mcp connecting", "metadata"))
            elif startup_snapshot.mcp_failed:
                segments.append(StatusFooterSegment("mcp failed", "metadata"))
        if startup_state is not None:
            startup_snapshot = startup_state.snapshot()
            if startup_snapshot.update_pending:
                segments.append(StatusFooterSegment("update checking", "metadata"))
        if background_tasks is not None:
            running_background_tasks = background_tasks.running_count()
            if running_background_tasks:
                segments.append(StatusFooterSegment(f"bg {running_background_tasks}", "loaded"))
    else:
        segments.append(StatusFooterSegment("cwd unknown", "metadata"))

    session_entry = _session_entry(project_root, session_id)
    segments.extend(
        [
        StatusFooterSegment(
            _format_context_window_status(
                session_entry,
                settings.context.window_tokens,
                settings.context.resolved_compact_threshold,
            ),
            "context",
        ),
        StatusFooterSegment(_format_session_cache_hit_rate(session_entry), "context"),
        ]
    )
    return StatusFooter(tuple(segments)).with_active(active_work)


def _audit_mode_label(audit_mode: AuditModeState | str | None, settings: Settings) -> str:
    if isinstance(audit_mode, AuditModeState):
        return audit_mode.mode.value
    if isinstance(audit_mode, str) and audit_mode:
        return audit_mode
    return settings.audit.mode.value


def _format_session_cache_hit_rate(session_entry: SessionEntry | None) -> str:
    if session_entry is None:
        return "cache --"
    hit_rate = format_cache_hit_rate(session_entry.cache_usage)
    if hit_rate == "unknown":
        return "cache --"
    return f"cache {hit_rate}"


def _format_session_cache_for_list(entry: SessionEntry) -> str:
    parts = []
    if entry.cache_prefix_generation:
        parts.append(f"gen {entry.cache_prefix_generation}")
    usage = format_cache_usage(entry.cache_usage)
    if usage != "unknown":
        parts.append(usage)
    if entry.cache_break_reason:
        parts.append(f"break {entry.cache_break_reason}")
    return " · ".join(parts) if parts else "unknown"


def _format_context_window_status(
    session_entry: SessionEntry | None,
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
        usage = (
            context_window_usage(usage_payload)
            if isinstance(usage_payload, dict) and usage_payload.get("request_usage_entries")
            else None
        )
        used_tokens = usage.used_tokens if usage is not None else None
    if used_tokens is None:
        return f"ctx unknown/{window_text}"
    percentage = used_tokens / window_tokens * 100
    status = f"ctx {_format_token_count_short(used_tokens)}/{window_text} ({percentage:.1f}%)"
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


def _format_stream_token_count_short(value: int) -> str:
    if value >= 1_000:
        precision = 1 if value < 100_000 else 0
        formatted = f"{value / 1_000:.{precision}f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return f"{formatted}K"
    return str(value)


def _format_turn_usage_line(usage: TokenUsage) -> str:
    prefix = f"requests {usage.requests:,} · " if usage.requests > 0 else ""
    return f"{prefix}{format_usage_line(usage)}"


def _refresh_working_status(
    renderer: TerminalStreamRenderer,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(RUNTIME_STATUS_REFRESH_SECONDS):
        renderer.refresh_status()


@contextlib.contextmanager
def _status_display(
    console: Console,
    initial_status: Text,
    *,
    palette: UiPalette,
):
    if _should_use_inline_runtime_status(console):
        output_lock = threading.RLock()
        status = _InlineRuntimeStatus(console, palette=palette, output_lock=output_lock)
        status.update(initial_status)
        try:
            yield status
        finally:
            status.clear()
        return

    yield _SilentStatus()


@contextlib.contextmanager
def _phase_status_display(
    console: Console,
    status_text: Text,
    *,
    palette: UiPalette,
):
    if not _should_use_inline_runtime_status(console):
        yield _SilentStatus()
        return
    status = _InlineRuntimeStatus(console, palette=palette)
    status.update(status_text)
    try:
        yield status
    finally:
        status.clear()


def _should_use_inline_runtime_status(console: Console) -> bool:
    isatty = getattr(console.file, "isatty", None)
    return bool(callable(isatty) and isatty())


class _InlineRuntimeStatus:
    inline_output_flow = True
    periodic_refresh = True

    def __init__(
        self,
        console: Console,
        *,
        palette: UiPalette,
        output_lock: Any | None = None,
    ) -> None:
        self.console = console
        self.palette = palette
        self.columns = 0
        self.output_lock = output_lock or threading.RLock()
        self.active = False

    def update(self, status: Text) -> None:
        with self.output_lock:
            columns = _terminal_columns(self.console)
            self.columns = columns
            self._write_line(status.plain)
            self.console.file.flush()

    def clear(self) -> None:
        with self.output_lock:
            if not self.active:
                return
            self.console.file.write("\r\x1b[2K")
            self.active = False
            self.console.file.flush()

    def clear_for_output(self) -> None:
        self.clear()

    def _write_line(self, text: str) -> None:
        width = max(self.columns - 1, 1)
        padded = _fit_status_line(text, width=width)
        self.console.file.write("\r\x1b[2K")
        self.console.print(_style_runtime_status_line(padded, self.palette), end="")
        self.active = True


class _SilentStatus:
    def update(self, status: Text) -> None:
        return None


def _phase_status_text(text: str, palette: UiPalette) -> Text:
    return Text.assemble(
        ("• ", palette.toolbar_separator),
        (text, palette.toolbar_metadata),
    )


@dataclass(frozen=True)
class _RuntimeStatusSegments:
    prefix: str
    label: str = ""
    payload: str = ""


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_STATUS_SEPARATOR = " · "


def _style_runtime_status_line(text: str, palette: UiPalette) -> Text:
    trailing_spaces = len(text) - len(text.rstrip(" "))
    visible = text.rstrip(" ")
    segments = _parse_runtime_status_segments(visible)
    if segments is None:
        styled = Text(visible, style=palette.toolbar_metadata)
    else:
        styled = Text()
        _append_runtime_status_prefix(styled, segments.prefix, palette)
        if segments.label:
            _append_runtime_status_separator(styled, palette)
            styled.append(segments.label, style=palette.toolbar_active)
        if segments.payload:
            _append_runtime_status_separator(styled, palette)
            styled.append(segments.payload, style=palette.toolbar_metadata)
    if trailing_spaces:
        styled.append(" " * trailing_spaces)
    return styled


def _append_runtime_status_prefix(text: Text, prefix: str, palette: UiPalette) -> None:
    spinner = ""
    rest = prefix
    if not rest.startswith("time ") and " time " in rest:
        spinner, rest = rest.split(" ", 1)
    if spinner:
        text.append(spinner, style=palette.toolbar_active)
        text.append(" ", style=palette.toolbar_separator)
    if not rest.startswith("time "):
        text.append(rest, style=palette.toolbar_metadata)
        return
    elapsed_and_hint = rest.removeprefix("time ")
    elapsed, separator, hint = elapsed_and_hint.partition(_STATUS_SEPARATOR)
    text.append("time ", style=palette.toolbar_metadata)
    text.append(elapsed, style=palette.toolbar_identity)
    if separator:
        _append_runtime_status_separator(text, palette)
        text.append(hint, style=palette.warning)


def _append_runtime_status_separator(text: Text, palette: UiPalette) -> None:
    text.append(_STATUS_SEPARATOR, style=palette.toolbar_separator)


def _sanitize_status_line(text: str) -> str:
    stripped = _ANSI_ESCAPE_RE.sub("", text)
    stripped = stripped.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    stripped = _CONTROL_CHAR_RE.sub("", stripped)
    return re.sub(r" {2,}", " ", stripped).strip()


def _truncate_status_line(text: str, *, max_width: int) -> str:
    if cell_len(text) <= max_width:
        return text
    if max_width <= 1:
        return "…" if max_width == 1 else ""
    suffix = "…"
    available = max_width - cell_len(suffix)
    used = 0
    result: list[str] = []
    for char in text:
        char_width = cell_len(char)
        if used + char_width > available:
            break
        result.append(char)
        used += char_width
    return "".join(result).rstrip() + suffix


def _fit_status_line(text: str, *, width: int) -> str:
    width = max(width, 0)
    sanitized = _sanitize_status_line(text)
    segments = _parse_runtime_status_segments(sanitized)
    line = (
        _fit_runtime_status_segments(segments, width=width)
        if segments is not None
        else _truncate_status_line(sanitized, max_width=width)
    )
    return line + (" " * max(0, width - cell_len(line)))


def _parse_runtime_status_segments(text: str) -> _RuntimeStatusSegments | None:
    interrupt = "esc to interrupt"
    interrupt_index = text.find(interrupt)
    if interrupt_index < 0:
        return None

    prefix_end = interrupt_index + len(interrupt)
    prefix = text[:prefix_end].strip()
    detail = text[prefix_end:]
    if detail.startswith(_STATUS_SEPARATOR):
        detail = detail[len(_STATUS_SEPARATOR) :].strip()
    else:
        detail = detail.strip()
    if not detail:
        return _RuntimeStatusSegments(prefix=prefix)

    if detail.startswith(f"local command{_STATUS_SEPARATOR}"):
        payload = detail.removeprefix(f"local command{_STATUS_SEPARATOR}").strip()
        return _RuntimeStatusSegments(prefix=prefix, label="local command", payload=payload)

    tool_match = re.match(r"(tool \[[^\]]+\])(?:\s+(.*))?$", detail)
    if tool_match:
        label, payload = tool_match.groups()
        payload_text = (payload or "").strip()
        if payload_text.startswith("·"):
            payload_text = payload_text.removeprefix("·").strip()
        return _RuntimeStatusSegments(prefix=prefix, label=label, payload=payload_text)

    return _RuntimeStatusSegments(prefix=prefix, label=detail)


def _fit_runtime_status_segments(segments: _RuntimeStatusSegments, *, width: int) -> str:
    if width <= 0:
        return ""

    full = _runtime_status_segments_text(segments)
    if cell_len(full) <= width:
        return full

    if cell_len(segments.prefix) >= width:
        return _truncate_status_line(segments.prefix, max_width=width)

    if not segments.label:
        return _truncate_status_line(segments.prefix, max_width=width)

    prefix_label = f"{segments.prefix}{_STATUS_SEPARATOR}{segments.label}"
    if segments.payload:
        base = f"{prefix_label}{_STATUS_SEPARATOR}"
        payload_width = width - cell_len(base)
        if payload_width > 0:
            payload = _truncate_status_line(segments.payload, max_width=payload_width)
            return f"{base}{payload}".rstrip()

    if cell_len(prefix_label) <= width:
        return prefix_label

    label_base = f"{segments.prefix}{_STATUS_SEPARATOR}"
    label_width = width - cell_len(label_base)
    if label_width > 0:
        label = _truncate_status_line(segments.label, max_width=label_width)
        return f"{label_base}{label}".rstrip()

    return _truncate_status_line(segments.prefix, max_width=width)


def _runtime_status_segments_text(segments: _RuntimeStatusSegments) -> str:
    parts = [segments.prefix]
    if segments.label:
        parts.append(segments.label)
    if segments.payload:
        parts.append(segments.payload)
    return _STATUS_SEPARATOR.join(parts)


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
            detail_before_interrupt=True,
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
    detail_before_interrupt: bool = False,
) -> Text:
    text = Text()
    if spinner:
        text.append(spinner, style=palette.toolbar_active)
        text.append(" ", style=palette.toolbar_separator)
    text.append("time ", style=palette.toolbar_metadata)
    text.append(elapsed, style=palette.toolbar_identity)
    if detail and (detail_before_interrupt or detail.startswith("↓ ")):
        _append_runtime_status_separator(text, palette)
        _append_runtime_detail(text, detail, palette)
        _append_runtime_status_separator(text, palette)
        text.append("esc to interrupt", style=palette.warning)
    else:
        _append_runtime_status_separator(text, palette)
        text.append("esc to interrupt", style=palette.warning)
        if detail:
            _append_runtime_status_separator(text, palette)
            _append_runtime_detail(text, detail, palette)
    return text


def _append_runtime_detail(text: Text, detail: str, palette: UiPalette) -> None:
    tool_match = re.match(r"(tool \[[^\]]+\])(?:\s+(.*))?$", detail)
    if tool_match:
        label, payload = tool_match.groups()
        text.append(label, style=palette.toolbar_active)
        if payload:
            text.append(" ", style=palette.toolbar_separator)
            text.append(payload, style=palette.toolbar_metadata)
        return
    text.append(detail, style=palette.toolbar_active)


def _runtime_spinner_frame(started_at: float) -> str:
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    index = int(max(0.0, time.monotonic() - started_at)) % len(frames)
    return frames[index]


def _runtime_tool_activity_name(tool_name: str) -> str:
    if tool_name.startswith("mcp_"):
        return "MCP"
    return format_tool_display_name(tool_name)


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


def _print_submitted_user_input(console: Console, text: str, *, palette: UiPalette | None = None) -> None:
    _clear_submitted_prompt_echo(console, text)
    _print_user_input(console, text, palette=palette)


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
    with _phase_status_display(
        console,
        _phase_status_text("rendering response", palette),
        palette=palette,
    ):
        rendered = render_markdown(text.rstrip(), palette=palette, width=console.width)
    console.print()
    console.print(_status_line("[Assistant]", palette.assistant))
    console.print(rendered)


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
        tool_name = event.name or "tool"
        arguments = _string_payload(event.payload.get("arguments"))
        call_id = ""
        is_subagent = tool_name.startswith("subagent_")
        summary = (
            format_tool_display_label(tool_name)
            if is_subagent
            else format_tool_call_summary(
                tool_name,
                arguments,
                project_root=project_root,
            )
        )
        if pending_tool_calls is not None:
            call_id = _string_payload(event.payload.get("call_id"))
            if call_id:
                pending_tool_calls[call_id] = ToolCallDisplay(
                    summary=summary,
                    name=tool_name,
                )
        if is_subagent:
            console.print(_status_line(f"{summary} started", palette.info))
            task = _subagent_input_markdown(arguments)
            if task:
                console.print(_subagent_input_panel(task, palette=palette, width=console.width))
        if reasoning_sink is not None:
            reasoning_sink.set_tool_status(tool_name)
        return
    if event.kind == "tool_output":
        if reasoning_sink is not None:
            reasoning_sink.flush()
        view = parse_tool_output(event.text)
        call_id = _string_payload(event.payload.get("call_id"))
        call = pending_tool_calls.pop(call_id, None) if pending_tool_calls is not None else None
        call_summary = call.summary if call is not None else ""
        summary = (
            _audit_rejection_tool_summary(call.name if call is not None else view.name)
            if _is_audit_rejection_tool_output(event.text, view)
            else format_tool_progress_summary(call_summary, event.text)
        )
        diff = render_tool_diff_preview(
            event.text,
            palette=palette,
            width=console.width,
            project_root=project_root,
        )
        if not should_omit_success_summary(view, diff):
            console.print(_status_line(summary, tool_status_style(view, palette)))
        if _should_print_tool_output_debug(view):
            console.print(Text("Tool output JSON:", style=palette.muted))
            console.print(Text(_format_tool_output_debug(event.text), style=palette.muted))
        shell_output = render_shell_output_block(event.text, palette=palette, width=console.width)
        if shell_output:
            console.print(shell_output)
        todo_board = render_todo_board(event.text, palette=palette, width=console.width)
        if todo_board:
            console.print(todo_board)
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


def _stream_event_writes_terminal(event: DeepyStreamEvent) -> bool:
    if event.kind == "reasoning_delta":
        return bool(event.text)
    if event.kind == "tool_call":
        return bool((event.name or "").startswith("subagent_"))
    return event.kind in {"tool_output", "status"}


def _is_audit_rejection_tool_output(output: str, view: ToolOutputView) -> bool:
    if view.ok is True:
        return False
    normalized = output.strip().lower()
    return "audit approval" in normalized and "reject" in normalized


def _audit_rejection_tool_summary(tool_name: str) -> str:
    return f"{format_tool_display_label(tool_name or 'tool')} rejected"


def _silent_generation_status_detail(event: DeepyStreamEvent) -> str | None:
    if event.kind in {"text_delta", "message"} and event.text:
        return ""
    if event.kind == "raw_response" and event.text:
        return ""
    return None


def _string_payload(value: object) -> str:
    return value if isinstance(value, str) else ""


def _subagent_input_markdown(arguments: str) -> str:
    if not arguments.strip():
        return ""
    try:
        parsed = json_utils.loads(arguments)
    except json_utils.JSONDecodeError:
        return arguments.strip()
    if not isinstance(parsed, dict):
        return arguments.strip()
    for key in ("input", "task", "prompt", "request"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in parsed.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _subagent_input_panel(
    text: str,
    *,
    palette: UiPalette,
    width: int,
) -> Panel:
    return Panel(
        render_markdown(text, palette=palette, width=max(24, width - 6)),
        title="Subagent Parameters",
        border_style=palette.info,
        padding=(0, 1),
        expand=False,
    )


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
