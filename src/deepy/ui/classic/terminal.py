from __future__ import annotations

import asyncio
import contextlib
import os
import queue
import re
import select
import shutil
import threading
import time
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

from deepy import __version__
from deepy.audit import ApprovalDecision, AuditModeState, AuditPolicy, PendingApproval
from deepy.background_tasks import BackgroundTaskManager
from deepy.format_tokens import (
    format_stream_token_count_short as _format_stream_token_count_short,
    format_token_count_short as _format_token_count_short,
)
from deepy.utils.clock import now_ms as _now_ms
from deepy.config import (
    Settings,
    load_settings,
    ui_theme_from_selection,
    ui_theme_number,
    update_config_theme,
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
from deepy.llm.multimodal import (
    format_user_prompt_display,
    supports_image_input,
)
from deepy.mcp import DeepyMcpRuntime, format_mcp_status, teardown_mcp_after_startup
from deepy.prompts.init_agents import build_agents_init_prompt
from deepy.prompts.rules import has_agents_instructions
from deepy.sessions import DeepySession, SessionEntry, list_session_entries
from deepy.session_cost import (
    balance_snapshot_to_dict,
    should_track_session_cost,
    supports_session_cost,
)
from deepy.sessions.manager import DeepySessionManager
from deepy.skills import discover_skills, find_skill
from deepy.status import (
    BalanceStatus,
    build_status_report,
    fetch_deepseek_balance,
    format_compact_status_report,
)
from deepy.update_check import VersionUpdate
from deepy.update_check import check_for_version_update
from deepy.ui.shared.input.commands import SlashCommand, parse_slash_command
from deepy.ui.shared.input.ask_user_question import OTHER_VALUE
from deepy.ui.shared.input.ask_user_question import AskUserQuestionItem
from deepy.ui.shared.input.ask_user_question import AskUserQuestionOptionEntry
from deepy.ui.shared.input.ask_user_question import build_answer_for_question
from deepy.ui.shared.input.ask_user_question import build_options
from deepy.ui.shared.input.ask_user_question import format_ask_user_question_answers
from deepy.ui.shared.input.ask_user_question import format_ask_user_question_decline
from deepy.ui.shared.input.ask_user_question import normalize_questions
from deepy.ui.classic.pickers.audit_approval_picker import AUDIT_APPROVAL_APPROVE
from deepy.ui.classic.pickers.audit_approval_picker import pick_audit_approval
from deepy.ui.shared.render.exit_summary import build_exit_summary_text
from deepy.ui.shared.local_command import (
    LocalCommandInput,
    build_synthetic_shell_transcript_items,
    parse_local_command,
    run_local_command,
    shell_tool_result_json,
)
from deepy.ui.shared.input.image_input import ImageAttachmentController
from deepy.ui.shared.render.message_view import (
    ToolOutputView,
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
from deepy.ui.classic.status.background_tasks import (
    _format_background_tasks_for_terminal,
    _stop_background_tasks_for_terminal,
)
from deepy.ui.classic.status.approval_render import _approval_panel as _approval_panel
from deepy.ui.classic.status.approval_render import (
    _approval_panel_ansi,
    _approval_panel_state,
)
from deepy.ui.classic.status.transcript_parse import (
    _chat_tool_calls,
    _item_text,
    _reasoning_text,
    _tool_output_text,
)
from deepy.ui.classic.commands.config_choices import (
    _print_theme_choices,
)
from deepy.ui.classic.status.runtime_status import (
    _ANSI_ESCAPE_RE as _ANSI_ESCAPE_RE,
    _fit_status_line as _fit_status_line,
    _local_command_status_text as _local_command_status_text,
    _runtime_spinner_frame as _runtime_spinner_frame,
    _style_runtime_status_line as _style_runtime_status_line,
)
from deepy.ui.classic.status.runtime_status import (
    _STATUS_SEPARATOR,
    _format_duration_ms,
    _phase_status_text,
    _runtime_tool_activity_name,
    _working_status_text,
)
from deepy.ui.classic.commands.skill_commands import (
    _build_installed_skill_views as _build_installed_skill_views,
    _handle_skill_menu_action as _handle_skill_menu_action,
    _handle_skills_command,
)
from deepy.ui.classic.commands.config_commands import (
    _handle_input_suggestion_command,
    _handle_theme_command,
    _handle_ui_command,
    _handle_view_command,
)
from deepy.ui.classic.commands.config_setup import _handle_reset_command
from deepy.ui.classic.commands.model_commands import (
    _handle_model_command,
)
from deepy.ui.classic.markdown import render_markdown
from deepy.ui.shared.session.session_transcript import (
    history_tool_call_event as _history_tool_call_event,
    history_tool_output_event,
    item_type as _item_type,
    role as _role,
    session_status,
    session_title,
)
from deepy.ui.classic.prompt.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.classic.prompt.prompt_input import build_prompt_toolbar, create_prompt_session, measure_text_rows, prompt_for_input
from deepy.ui.shared.session.session_list import resolve_session_selection
from deepy.ui.shared.session.session_picker import ResumeSessionPreview
from deepy.ui.shared.session.session_picker import format_resume_session_choices
from deepy.ui.shared.session.session_picker import pick_resume_session
from deepy.ui.shared.input.slash_commands import build_slash_commands
from deepy.ui.shared.input.slash_commands import build_subagent_slash_prompt
from deepy.ui.shared.input.slash_commands import is_builtin_slash_command
from deepy.ui.shared.input.slash_commands import is_subagent_slash_command
from deepy.ui.classic.status.status_footer import StatusFooter, StatusFooterSegment
from deepy.ui.shared.render.styles import (
    DARK_PALETTE,
    UiPalette,
    resolve_ui_palette,
    status_style,
)
from deepy.ui.shared.render.welcome import build_welcome_panel, format_home_relative_path
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

    async def teardown(self, mcp_runtime: DeepyMcpRuntime) -> None:
        await teardown_mcp_after_startup(mcp_runtime, self._future)


@dataclass(frozen=True)
class ToolCallDisplay:
    summary: str
    name: str


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
    image_attachments = ImageAttachmentController(
        supports_image_input=supports_image_input(settings)
    )
    prompt_session = _create_interactive_prompt_session(
        root,
        palette,
        loaded_skill_names,
        input_suggestions=input_suggestions,
        audit_state=audit_state,
        image_attachments=image_attachments,
        on_image_paste_notice=lambda message: _print_assistant_output(
            output,
            message,
            palette=palette,
        ),
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
                    image_attachments=image_attachments,
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
            text, pasted_images = image_attachments.collect_from_prompt_text(text)
            if not text and not pasted_images:
                continue

            local_command = parse_local_command(text) if not pasted_images else None
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

            slash = parse_slash_command(text) if not pasted_images else None
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
                    image_attachments.supports_image_input = supports_image_input(settings)
                    palette = resolve_ui_palette(settings.ui.theme)
                if slash.name == "input-suggestion":
                    settings = load_settings(settings.path) if settings.path is not None else settings
                    input_suggestions.set_enabled(settings.ui.input_suggestions_enabled)
                    image_attachments.supports_image_input = supports_image_input(settings)
                if slash.name == "ui":
                    settings = load_settings(settings.path) if settings.path is not None else settings
                if slash.name in {"skills", "theme", "ui", "reset", "model", "input-suggestion", "view"}:
                    prompt_session = _create_interactive_prompt_session(
                        root,
                        palette,
                        loaded_skill_names,
                        input_suggestions=input_suggestions,
                        audit_state=audit_state,
                        image_attachments=image_attachments,
                        on_image_paste_notice=lambda message: _print_assistant_output(
                            output,
                            message,
                            palette=palette,
                        ),
                    )
                session_id = next_session
                continue

            _print_submitted_user_input(
                output,
                format_user_prompt_display(text, pasted_images),
                palette=palette,
            )
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
                image_attachments=pasted_images,
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
        try:
            async_runner.run(mcp_startup.teardown(mcp_runtime))
        finally:
            async_runner.close()

def _create_interactive_prompt_session(
    root: Path,
    palette: UiPalette,
    loaded_skill_names: list[str],
    input_suggestions: InputSuggestionController | None = None,
    audit_state: AuditModeState | None = None,
    image_attachments: ImageAttachmentController | None = None,
    on_image_paste_notice: Callable[[str], None] | None = None,
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
        image_attachments=image_attachments,
        on_image_paste_notice=on_image_paste_notice,
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
    approved_preflight_diffs: set[str] = set()

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
            approved_preflight_diffs=approved_preflight_diffs,
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
                approved_preflight_diffs=approved_preflight_diffs,
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
    approved_preflight_diffs: set[str] | None = None,
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
                    approved_preflight_diffs=approved_preflight_diffs,
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
    approved_preflight_diffs: set[str] | None = None,
) -> bool:
    if suspend_interrupt_watcher is not None:
        suspend_interrupt_watcher.set()
    try:
        _prepare_terminal_approval_prompt(
            status=status,
            stop_status_refresh=stop_status_refresh,
            status_thread_getter=status_thread_getter,
        )
        preflight_diff = _print_preflight_diff(
            item,
            console=console,
            palette=palette,
            project_root=project_root,
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
        approved = choice == AUDIT_APPROVAL_APPROVE
        if approved and preflight_diff is not None and approved_preflight_diffs is not None:
            approved_preflight_diffs.add(preflight_diff)
        if item.preflight is not None and not approved:
            console.print(Text("Proposed change rejected.", style=palette.warning))
        return approved
    finally:
        if suspend_interrupt_watcher is not None:
            suspend_interrupt_watcher.clear()


def _print_preflight_diff(
    item: PendingApproval,
    *,
    console: Console,
    palette: UiPalette,
    project_root: str | Path | None,
) -> str | None:
    if item.preflight is None:
        return None
    output = json_utils.dumps(item.preflight)
    diff_text = _tool_output_diff_text(output)
    if diff_text is None:
        return None
    diff = render_tool_diff_preview(
        output,
        max_lines=120,
        palette=palette,
        width=console.width,
        project_root=str(project_root) if project_root is not None else None,
    )
    if diff is None:
        return None
    console.print(_status_line("Proposed Change", palette.warning))
    console.print(diff)
    return diff_text


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
        approved_preflight_diffs: set[str] | None = None,
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
        self.approved_preflight_diffs = approved_preflight_diffs

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
                approved_preflight_diffs=self.approved_preflight_diffs,
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
                approved_preflight_diffs=self.approved_preflight_diffs,
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
        console.print("/ui         Show or change Classic/Modern UI")
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
    if command.name == "ui":
        return _handle_ui_command(command, console, current_session_id, settings, palette, input_func=input_func)
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


def _history_tool_output_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return history_tool_output_event(item, _tool_output_text)


def _load_session_items(project_root: Path, session_id: str) -> list[dict[str, Any]]:
    try:
        return asyncio.run(DeepySession.open(project_root, session_id).get_items())
    except Exception:
        return []


def _session_title(items: list[dict[str, Any]]) -> str:
    return session_title(items, _item_text)


def _session_status(items: list[dict[str, Any]]) -> str:
    return session_status(items, _tool_output_text)


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
    approved_preflight_diffs: set[str] | None = None,
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
        diff_text = _tool_output_diff_text(event.text)
        suppress_preflight_diff = (
            diff_text is not None
            and approved_preflight_diffs is not None
            and diff_text in approved_preflight_diffs
        )
        diff = None if suppress_preflight_diff else render_tool_diff_preview(
            event.text,
            palette=palette,
            width=console.width,
            project_root=project_root,
        )
        if suppress_preflight_diff and diff_text is not None and approved_preflight_diffs is not None:
            approved_preflight_diffs.discard(diff_text)
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


def _tool_output_diff_text(output: str) -> str | None:
    view = parse_tool_output(output)
    if view.ok is not True:
        return None
    return view.diff_preview or view.diff


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
