from __future__ import annotations

from collections.abc import Sequence

from deepy.background_tasks import BackgroundTaskSnapshot
from deepy.sessions import SessionEntry
from deepy.ui.modern.app_helpers import _load_session_items
from deepy.ui.modern.render.transcript_items import (
    _format_tui_session_label,
    _session_status,
    _session_title,
)
from deepy.ui.modern.app_patchable import resolve as _resolve
from deepy.ui.modern.app_state_proto import AppStateProto
from deepy.ui.modern.background_tasks_tui import _parse_tui_background_stop_selection
from deepy.ui.modern.screens import Choice, ChoiceScreen
from deepy.ui.modern.state import reset_turn_buffers, set_pending_questions, set_session_id
from deepy.ui.modern.widgets import ErrorBlock, InfoBlock
from deepy.ui.shared.session.session_picker import ResumeSessionPreview


class AppSessionsMixin(AppStateProto):
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
        self._refresh_status_session_entry()
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
        entries = {entry.id for entry in _resolve("list_session_entries")(self.project_root)}
        if target not in entries:
            await self._append_block(ErrorBlock(f"Session not found: {target}"))
            return
        self.state = set_session_id(self.state, target)
        self._refresh_status_session_entry()
        await self._restore_transcript(target)
        self._update_status(f"Resumed {target}")


    async def _choose_session(self, title: str) -> str | None:
        entries = _resolve("list_session_entries")(self.project_root)
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
        manager = _resolve("DeepySessionManager")(
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
        self._refresh_status_session_entry()
        self._update_status("Idle")


