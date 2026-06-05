from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.text import Text

from deepy.audit import ApprovalDecision, PendingApproval
from deepy.config import Settings
from deepy.mcp import DeepyMcpRuntime
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.sessions import DeepySession
from deepy.ui.classic.esc_watch import _esc_interrupt_watcher
from deepy.ui.classic.footer import _build_status_footer
from deepy.ui.classic.pickers.audit_approval_picker import AUDIT_APPROVAL_APPROVE
from deepy.ui.classic.printing import (
    _print_submitted_user_input,
    _status_line,
    _tool_output_diff_text,
)
from deepy.ui.classic.runtime_workers import _MainThreadCallbackBridge
from deepy.ui.classic.status.approval_render import _approval_panel_ansi, _approval_panel_state
from deepy.ui.classic.status.runtime_status import _local_command_status_text
from deepy.ui.classic.status_display import _status_display
from deepy.ui.shared.local_command import (
    LocalCommandInput,
    build_synthetic_shell_transcript_items,
    shell_tool_result_json,
)
from deepy.ui.shared.render.message_view import (
    format_tool_call_summary,
    format_tool_progress_summary,
    render_shell_output_block,
    )
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette, resolve_ui_palette, status_style
from deepy.utils import json as json_utils


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
        choice = _resolve("pick_audit_approval")(
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
    diff = _resolve("render_tool_diff_preview")(
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
            result = _resolve("run_local_command")(
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

