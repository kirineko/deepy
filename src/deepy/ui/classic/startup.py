from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

from deepy import __version__
from deepy.audit import AuditPolicy, AuditModeState
from deepy.config import Settings, load_settings, update_config_theme
from deepy.input_suggestions import InputSuggestion, InputSuggestionController, generate_input_suggestion, is_eligible_for_input_suggestion
from deepy.llm.runner import RunSummary
from deepy.mcp import DeepyMcpRuntime
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.sessions import DeepySession
from deepy.skills import discover_skills

from deepy.ui.classic.runtime_workers import _StartupState
from deepy.ui.shared.input.image_input import ImageAttachmentController
from deepy.ui.shared.input.slash_commands import build_slash_commands
from deepy.ui.shared.render.styles import UiPalette
from deepy.update_check import VersionUpdate
from deepy.ui.classic.terminal_types import VersionUpdateChecker


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

    return _resolve("create_prompt_session")(
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
        return _resolve("DeepyMcpRuntime")(settings, project_root=project_root, audit_policy=audit_policy)
    except TypeError as exc:
        if "audit_policy" not in str(exc):
            raise
        return _resolve("DeepyMcpRuntime")(settings, project_root=project_root)


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
    theme = _resolve("_prompt_theme_choice")(settings.ui.theme)
    update_config_theme(settings.path, theme)
    return load_settings(settings.path)


def load_theme_settings(settings: Settings) -> Settings:
    if settings.path is None:
        return settings
    try:
        return load_settings(settings.path)
    except Exception:
        return settings

