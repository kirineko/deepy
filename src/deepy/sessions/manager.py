from __future__ import annotations

import os
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepy.config import Settings, load_settings
from deepy.llm.compaction import CompactionResult, compact_session
from deepy.llm.provider import ProviderBundle
from deepy.llm.runner import RunSummary, run_prompt_once
from deepy.utils import json as json_utils

from .jsonl import DeepyJsonlSession, list_session_entries, project_sessions_dir


@dataclass(frozen=True)
class InterruptSummary:
    session_id: str
    killed_pids: list[int]
    failed_pids: list[int]


@dataclass
class DeepySessionManager:
    project_root: Path
    settings: Settings | None = None
    provider: ProviderBundle | None = None
    deepy_home: Path | None = None
    active_session_id: str | None = None
    _interrupted_sessions: set[str] = field(default_factory=set, init=False, repr=False)

    async def handle_user_prompt(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        **run_kwargs: Any,
    ) -> RunSummary:
        target_session = session_id or self.active_session_id
        if target_session:
            return await self.reply_session(target_session, prompt, **run_kwargs)
        return await self.create_session(prompt, **run_kwargs)

    async def create_session(self, prompt: str, **run_kwargs: Any) -> RunSummary:
        summary = await self._run(prompt, session_id=None, **run_kwargs)
        self.active_session_id = summary.session_id
        return summary

    async def reply_session(
        self,
        session_id: str,
        prompt: str,
        **run_kwargs: Any,
    ) -> RunSummary:
        self.activate_session(session_id)
        return await self._run(prompt, session_id=session_id, **run_kwargs)

    def activate_session(self, session_id: str) -> None:
        if not session_id:
            raise ValueError("session_id is required.")
        self.active_session_id = session_id

    async def append_sdk_items(self, session_id: str, items: list[dict[str, Any]]) -> None:
        session = DeepyJsonlSession.open(
            self.project_root,
            session_id,
            deepy_home=self.deepy_home,
        )
        await session.add_items(items)

    async def compact_session(
        self,
        session_id: str,
        *,
        focus_instruction: str | None = None,
    ) -> CompactionResult:
        session = DeepyJsonlSession.open(
            self.project_root,
            session_id,
            deepy_home=self.deepy_home,
        )
        return await compact_session(
            session,
            self.settings or load_settings(),
            provider=self.provider,
            reason="manual",
            focus_instruction=focus_instruction,
        )

    def interrupt_active_session(self) -> InterruptSummary | None:
        if not self.active_session_id:
            return None
        return self.interrupt_session(self.active_session_id)

    def interrupt_session(self, session_id: str) -> InterruptSummary:
        self._interrupted_sessions.add(session_id)
        processes = _session_processes(self.project_root, session_id, self.deepy_home)
        killed_pids, failed_pids = _kill_processes(processes)
        _clear_session_processes(self.project_root, session_id, self.deepy_home)
        return InterruptSummary(
            session_id=session_id,
            killed_pids=killed_pids,
            failed_pids=failed_pids,
        )

    async def _run(
        self,
        prompt: str,
        *,
        session_id: str | None,
        **run_kwargs: Any,
    ) -> RunSummary:
        effective_session_id = session_id

        def should_interrupt() -> bool:
            return bool(effective_session_id and effective_session_id in self._interrupted_sessions)

        summary = await run_prompt_once(
            prompt,
            project_root=self.project_root,
            settings=self.settings or load_settings(),
            provider=self.provider,
            session_id=effective_session_id,
            should_interrupt=should_interrupt if effective_session_id else None,
            **run_kwargs,
        )
        if effective_session_id is None:
            effective_session_id = summary.session_id
        if summary.interrupted:
            self._interrupted_sessions.discard(effective_session_id)
        self.active_session_id = summary.session_id
        return summary


def _session_processes(
    project_root: Path,
    session_id: str,
    deepy_home: Path | None,
) -> dict[str, dict[str, str]]:
    for entry in list_session_entries(project_root, deepy_home=deepy_home):
        if entry.id == session_id and isinstance(entry.processes, dict):
            return entry.processes
    return {}


def _kill_processes(processes: dict[str, dict[str, str]]) -> tuple[list[int], list[int]]:
    killed_pids: list[int] = []
    failed_pids: list[int] = []
    for raw_pid in processes:
        try:
            pid = int(raw_pid)
        except ValueError:
            continue
        if _kill_process_group(pid) or _kill_process(pid):
            killed_pids.append(pid)
        else:
            failed_pids.append(pid)
    return killed_pids, failed_pids


def _kill_process_group(pid: int) -> bool:
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        return False
    return True


def _kill_process(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return False
    return True


def _clear_session_processes(
    project_root: Path,
    session_id: str,
    deepy_home: Path | None,
) -> None:
    index_path = project_sessions_dir(project_root, deepy_home) / "sessions-index.json"
    if not index_path.is_file():
        return
    try:
        raw = json_utils.loads(index_path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return
    changed = False
    entries = raw.get("sessions")
    if not isinstance(entries, list):
        return
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == session_id:
            entry["processes"] = None
            changed = True
    if changed:
        index_path.write_text(json_utils.dumps_pretty(raw) + "\n", encoding="utf-8")
