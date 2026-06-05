from __future__ import annotations

# Re-exports below are the classic TUI test monkeypatch surface; keep even if unused here.
# ruff: noqa: F401

import asyncio
import shutil
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.text import Text

from deepy import __version__
from deepy.audit import ApprovalDecision, AuditModeState, AuditPolicy, PendingApproval
from deepy.config import Settings, load_settings
from deepy.input_suggestions import InputSuggestionController
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.multimodal import format_user_prompt_display, supports_image_input
from deepy.llm.runner import RunSummary, run_prompt_once
from deepy.prompts.init_agents import build_agents_init_prompt
from deepy.skills import discover_skills, find_skill
from deepy.update_check import VersionUpdate, check_for_version_update
from deepy.ui.classic.approvals import (
    _collect_terminal_approval_decision,
    _handle_local_command,
    _terminal_approval_resolver,
)
from deepy.ui.classic.commands.skill_commands import (
    _build_installed_skill_views,
    _handle_skill_menu_action,
)
from deepy.ui.classic.esc_watch import (
    _cleanup_background_tasks,
    _esc_interrupt_watcher,
    _prompt_for_background_stop_selection,
    _watch_windows_esc_keypress,
)
from deepy.ui.classic.pickers.audit_approval_picker import AUDIT_APPROVAL_APPROVE
from deepy.ui.classic.status.approval_render import _approval_panel, _approval_panel_state
from deepy.ui.classic.exit_summary import (
    _capture_session_cost_start,
    _print_exit_summary,
    _record_session_cost_start,
)
from deepy.ui.classic.footer import (
    _build_prompt_toolbar_provider,
    _build_status_footer,
    _format_context_footer,
    _print_usage_footer,
)
from deepy.ui.classic.printing import (
    _clear_submitted_prompt_echo,
    _print_assistant_output,
    _print_submitted_user_input,
    _print_stream_event,
    _print_user_input,
    _status_line,
    _submitted_prompt_echo_rows,
)
from deepy.ui.classic.status.transcript_parse import _tool_output_text
from deepy.ui.classic.questions import _collect_pending_question_response
from deepy.ui.classic.runtime_workers import (
    _AsyncRuntimeWorker,
    _MainThreadCallbackBridge,
    _McpStartupHandle,
    _StartupState,
    ToolCallDisplay,
)
from deepy.ui.classic.slash_commands import _handle_slash_command
from deepy.ui.classic.startup import (
    _connect_mcp_for_startup,
    _create_interactive_prompt_session,
    _create_mcp_runtime,
    _ensure_interactive_theme,
    _flush_startup_notifications,
    _prepare_input_suggestion,
    _settle_startup_version_update_for_welcome,
    _start_background_version_update_check,
    load_theme_settings,
)
from deepy.format_tokens import (
    format_stream_token_count_short as _format_stream_token_count_short,
    format_token_count_short as _format_token_count_short,
)
from deepy.ui.classic.status.runtime_status import (
    _ANSI_ESCAPE_RE,
    _fit_status_line,
    _format_duration_ms,
    _local_command_status_text,
    _runtime_spinner_frame,
    _style_runtime_status_line,
    _working_status_text,
)
from deepy.ui.classic.status_display import (
    _InlineRuntimeStatus,
    _refresh_working_status,
    _SilentStatus,
    _status_display,
)
from deepy.ui.classic.stream_render import TerminalStreamRenderer
from deepy.ui.classic.terminal_types import (
    InputFunc,
    MAX_CLARIFICATION_ROUNDS_PER_TURN,
    RUNTIME_STATUS_REFRESH_SECONDS,
    RunOnce,
    VersionUpdateChecker,
)
from deepy.ui.classic import terminal_bindings
from deepy.ui.classic.prompt.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.shared.input.commands import parse_slash_command
from deepy.ui.shared.input.image_input import ImageAttachmentController
from deepy.ui.shared.input.slash_commands import (
    build_subagent_slash_prompt,
    is_builtin_slash_command,
    is_subagent_slash_command,
)
from deepy.ui.shared.local_command import parse_local_command
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette, resolve_ui_palette
from deepy.ui.shared.render.welcome import build_welcome_panel

BackgroundTaskManager = terminal_bindings.BackgroundTaskManager
DeepyMcpRuntime = terminal_bindings.DeepyMcpRuntime
create_prompt_session = terminal_bindings.create_prompt_session
estimate_tokens_for_text = terminal_bindings.estimate_tokens_for_text
fetch_deepseek_balance = terminal_bindings.fetch_deepseek_balance
list_session_entries = terminal_bindings.list_session_entries
msvcrt = terminal_bindings.msvcrt
pick_audit_approval = terminal_bindings.pick_audit_approval
prompt_for_input = terminal_bindings.prompt_for_input
render_markdown = terminal_bindings.render_markdown
render_tool_diff_preview = terminal_bindings.render_tool_diff_preview
run_local_command = terminal_bindings.run_local_command
_prompt_theme_choice = terminal_bindings._prompt_theme_choice

__all__ = [
    "BackgroundTaskManager",
    "DeepyMcpRuntime",
    "InputFunc",
    "MAX_CLARIFICATION_ROUNDS_PER_TURN",
    "RunOnce",
    "create_prompt_session",
    "estimate_tokens_for_text",
    "fetch_deepseek_balance",
    "list_session_entries",
    "load_theme_settings",
    "msvcrt",
    "pick_audit_approval",
    "prompt_for_input",
    "render_markdown",
    "render_tool_diff_preview",
    "run_interactive",
    "run_local_command",
    "_build_status_footer",
    "_collect_pending_question_response",
    "_format_context_footer",
    "_format_duration_ms",
    "_format_stream_token_count_short",
    "_format_token_count_short",
    "_handle_slash_command",
    "_print_assistant_output",
    "_print_stream_event",
    "_print_usage_footer",
    "_print_user_input",
    "_prompt_theme_choice",
    "_run_once_with_status",
    "_status_display",
    "_tool_output_text",
    "_working_status_text",
]


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


