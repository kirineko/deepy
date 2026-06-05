from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from rich.console import Console

from deepy.config import Settings
from deepy.session_cost import balance_snapshot_to_dict, should_track_session_cost, supports_session_cost
from deepy.sessions import DeepySession, SessionEntry
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.ui.shared.render.exit_summary import build_exit_summary_text
from deepy.utils.clock import now_ms as _now_ms

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
            (entry for entry in _resolve("list_session_entries")(project_root) if entry.id == session_id),
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
        _resolve("fetch_deepseek_balance")(settings),
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
        _resolve("fetch_deepseek_balance")(settings),
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
        for entry in _resolve("list_session_entries")(project_root)
    )

