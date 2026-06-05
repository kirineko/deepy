from __future__ import annotations

import asyncio
from typing import Any

from deepy.sessions import DeepySession, SessionEntry
from deepy.session_cost import balance_snapshot_to_dict, should_track_session_cost, supports_session_cost
from deepy.ui.modern.app_helpers import (
    _build_tui_status_context,
    _format_tui_side_status,
    _tui_session_entry,
)
from deepy.ui.modern.app_patchable import resolve as _resolve
from deepy.ui.modern.app_state_proto import AppStateProto
from deepy.ui.modern.state import set_quit_confirm, set_status
from deepy.ui.modern.widgets import StatusBar
from deepy.ui.shared.render.exit_summary import build_exit_summary_text
from deepy.utils.clock import now_ms as _now_ms
from textual.css.query import NoMatches
from textual.widgets import Static


class AppStatusMixin(AppStateProto):
    def _update_status(self, status: str) -> None:
        self.state = set_status(self.state, status)
        session_entry = self._cached_status_session_entry()
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
                session_entry=session_entry,
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
            session_entry=self._cached_status_session_entry(),
        )
        return context


    def _cached_status_session_entry(self) -> SessionEntry | None:
        if (
            not self._status_session_entry_loaded
            or self._status_session_entry_id != self.state.session_id
        ):
            self._refresh_status_session_entry()
        return self._status_session_entry


    def _refresh_status_session_entry(self) -> None:
        self._status_session_entry_id = self.state.session_id
        self._status_session_entry_loaded = True
        self._status_session_entry = _tui_session_entry(self.project_root, self.state.session_id)


    def _exit_with_summary(self) -> None:
        self._record_session_cost_end()
        self.exit_summary_text = self._build_exit_summary_text()
        self._cleanup_background_tasks()
        asyncio.create_task(self._shutdown_mcp_and_exit())


    async def _shutdown_mcp_and_exit(self) -> None:
        self.workers.cancel_group(self, "mcp-startup")
        await self.mcp_runtime.shutdown()
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
                    for entry in _resolve("list_session_entries")(self.project_root)
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
            _resolve("fetch_deepseek_balance")(self.settings),
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
            self._refresh_status_session_entry()


    def _record_session_cost_end(self) -> None:
        session_id = self.state.session_id
        if (
            not session_id
            or not should_track_session_cost(self.settings)
            or not self._session_cost_has_start(session_id)
        ):
            return
        snapshot = balance_snapshot_to_dict(
            _resolve("fetch_deepseek_balance")(self.settings),
            captured_at_ms=_now_ms(),
        )
        try:
            DeepySession.open(self.project_root, session_id).record_session_cost_end(snapshot)
        except Exception:
            return
        self._refresh_status_session_entry()


    def _session_cost_has_start(self, session_id: str) -> bool:
        return any(
            entry.id == session_id
            and isinstance(entry.session_cost, dict)
            and isinstance(entry.session_cost.get("start"), dict)
            for entry in _resolve("list_session_entries")(self.project_root)
        )


    def _clear_quit_confirm(self) -> None:
        if self.state.quit_confirm_pending:
            self.state = set_quit_confirm(self.state, False)
            self._update_status("Idle" if not self.state.busy else "Running")


