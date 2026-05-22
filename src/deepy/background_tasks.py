from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Sequence
from typing import Literal


BackgroundTaskStatus = Literal["running", "completed", "failed", "stopped"]
DEFAULT_MAX_RUNNING_TASKS = 4
DEFAULT_MAX_TERMINAL_TASKS = 32
DEFAULT_OUTPUT_PREVIEW_BYTES = 32 * 1024
DEFAULT_STOP_GRACE_SECONDS = 2.0


@dataclass(frozen=True)
class BackgroundTaskSnapshot:
    id: str
    command: str
    cwd: str
    status: BackgroundTaskStatus
    start_time: float
    output_path: Path
    pid: int | None = None
    end_time: float | None = None
    exit_code: int | None = None
    error: str | None = None
    stop_requested: bool = False

    @property
    def running(self) -> bool:
        return self.status == "running"


@dataclass(frozen=True)
class BackgroundTaskOutput:
    task: BackgroundTaskSnapshot
    output: str
    output_size_bytes: int
    output_preview_bytes: int
    output_truncated: bool
    more_available: bool


@dataclass(frozen=True)
class BackgroundTaskStopSummary:
    stopped: tuple[BackgroundTaskSnapshot, ...]
    not_found: tuple[str, ...] = ()


@dataclass
class _BackgroundTaskEntry:
    id: str
    command: str
    cwd: Path
    start_time: float
    output_path: Path
    process: subprocess.Popen[bytes] | None
    status: BackgroundTaskStatus = "running"
    pid: int | None = None
    end_time: float | None = None
    exit_code: int | None = None
    error: str | None = None
    stop_requested: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)

    def snapshot(self) -> BackgroundTaskSnapshot:
        with self.lock:
            return BackgroundTaskSnapshot(
                id=self.id,
                command=self.command,
                cwd=str(self.cwd),
                status=self.status,
                start_time=self.start_time,
                end_time=self.end_time,
                output_path=self.output_path,
                pid=self.pid,
                exit_code=self.exit_code,
                error=self.error,
                stop_requested=self.stop_requested,
            )


class BackgroundTaskError(RuntimeError):
    pass


class BackgroundTaskLimitError(BackgroundTaskError):
    pass


class BackgroundTaskManager:
    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        max_running_tasks: int = DEFAULT_MAX_RUNNING_TASKS,
        max_terminal_tasks: int = DEFAULT_MAX_TERMINAL_TASKS,
        stop_grace_seconds: float = DEFAULT_STOP_GRACE_SECONDS,
    ) -> None:
        root = base_dir or Path(tempfile.gettempdir()) / "deepy-background-tasks" / uuid.uuid4().hex
        self.base_dir = root
        self.max_running_tasks = max(1, max_running_tasks)
        self.max_terminal_tasks = max(0, max_terminal_tasks)
        self.stop_grace_seconds = max(0.0, stop_grace_seconds)
        self._entries: dict[str, _BackgroundTaskEntry] = {}
        self._lock = threading.RLock()
        self._next_id = 1
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def start(
        self,
        *,
        command: str,
        argv: Sequence[str],
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> BackgroundTaskSnapshot:
        with self._lock:
            running = sum(1 for entry in self._entries.values() if entry.status == "running")
            if running >= self.max_running_tasks:
                raise BackgroundTaskLimitError(
                    f"Background task limit reached ({self.max_running_tasks} running)."
                )
            task_id = self._new_task_id()
            output_path = self.base_dir / f"{task_id}.log"

        output_file = output_path.open("ab")
        entry: _BackgroundTaskEntry | None = None
        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
            output_file.close()
            entry = _BackgroundTaskEntry(
                id=task_id,
                command=command,
                cwd=cwd,
                start_time=time.time(),
                output_path=output_path,
                process=process,
                pid=process.pid,
            )
            with self._lock:
                self._entries[task_id] = entry
            thread = threading.Thread(target=self._wait_for_process, args=(entry,), daemon=True)
            thread.start()
            return entry.snapshot()
        except Exception:
            with contextlib.suppress(Exception):
                output_file.close()
            if entry is not None:
                with self._lock:
                    self._entries.pop(entry.id, None)
            raise

    def get(self, task_id: str) -> BackgroundTaskSnapshot | None:
        with self._lock:
            entry = self._entries.get(task_id)
        return entry.snapshot() if entry is not None else None

    def list(self, *, active_only: bool = False, limit: int | None = None) -> Sequence[BackgroundTaskSnapshot]:
        with self._lock:
            snapshots = [entry.snapshot() for entry in self._entries.values()]
        if active_only:
            snapshots = [snapshot for snapshot in snapshots if snapshot.status == "running"]
        snapshots.sort(
            key=lambda item: (
                0 if item.status == "running" else 1,
                -(item.start_time if item.status == "running" else item.end_time or item.start_time),
            )
        )
        return snapshots[:limit] if limit is not None else snapshots

    def has_running(self) -> bool:
        with self._lock:
            return any(entry.status == "running" for entry in self._entries.values())

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for entry in self._entries.values() if entry.status == "running")

    def read_output(
        self,
        task_id: str,
        *,
        max_bytes: int = DEFAULT_OUTPUT_PREVIEW_BYTES,
    ) -> BackgroundTaskOutput | None:
        snapshot = self.get(task_id)
        if snapshot is None:
            return None
        max_bytes = max(1, max_bytes)
        try:
            output_size = snapshot.output_path.stat().st_size if snapshot.output_path.exists() else 0
            offset = max(0, output_size - max_bytes)
            with snapshot.output_path.open("rb") as file:
                file.seek(offset)
                data = file.read(max_bytes)
        except OSError:
            output_size = 0
            data = b""
            offset = 0
        return BackgroundTaskOutput(
            task=snapshot,
            output=data.decode("utf-8", errors="replace"),
            output_size_bytes=output_size,
            output_preview_bytes=len(data),
            output_truncated=offset > 0,
            more_available=offset > 0,
        )

    def wait(self, task_id: str, *, timeout_seconds: float) -> BackgroundTaskSnapshot | None:
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while True:
            snapshot = self.get(task_id)
            if snapshot is None or snapshot.status != "running":
                return snapshot
            if time.monotonic() >= deadline:
                return snapshot
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def wait_for_output(self, task_id: str, *, timeout_seconds: float) -> BackgroundTaskSnapshot | None:
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while True:
            snapshot = self.get(task_id)
            if snapshot is None or snapshot.status != "running":
                return snapshot
            with contextlib.suppress(OSError):
                if snapshot.output_path.exists() and snapshot.output_path.stat().st_size > 0:
                    return snapshot
            if time.monotonic() >= deadline:
                return snapshot
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def stop(self, task_id: str, *, force_after_grace: bool = False) -> BackgroundTaskSnapshot | None:
        with self._lock:
            entry = self._entries.get(task_id)
        if entry is None:
            return None
        self._request_stop(entry)
        if force_after_grace:
            self._wait_or_force(entry, self.stop_grace_seconds)
        return entry.snapshot()

    def stop_all(self, *, force_after_grace: bool = True) -> BackgroundTaskStopSummary:
        with self._lock:
            entries = [entry for entry in self._entries.values() if entry.status == "running"]
        for entry in entries:
            self._request_stop(entry)
        if force_after_grace:
            for entry in entries:
                self._wait_or_force(entry, self.stop_grace_seconds)
        return BackgroundTaskStopSummary(stopped=tuple(entry.snapshot() for entry in entries))

    def _new_task_id(self) -> str:
        task_id = f"bg-{self._next_id}"
        self._next_id += 1
        return task_id

    def _wait_for_process(self, entry: _BackgroundTaskEntry) -> None:
        process = entry.process
        if process is None:
            return
        try:
            returncode = process.wait()
        except Exception as exc:
            self._settle(entry, "failed", error=str(exc))
            return
        if entry.snapshot().stop_requested:
            self._settle(entry, "stopped", exit_code=returncode)
        elif returncode == 0:
            self._settle(entry, "completed", exit_code=returncode)
        else:
            self._settle(entry, "failed", exit_code=returncode, error=f"Command exited with code {returncode}.")

    def _settle(
        self,
        entry: _BackgroundTaskEntry,
        status: BackgroundTaskStatus,
        *,
        exit_code: int | None = None,
        error: str | None = None,
    ) -> None:
        with entry.lock:
            if entry.status != "running":
                return
            entry.status = status
            entry.exit_code = exit_code
            entry.error = error
            entry.end_time = time.time()
        self._prune_terminal_entries()

    def _request_stop(self, entry: _BackgroundTaskEntry) -> None:
        with entry.lock:
            if entry.status != "running":
                return
            entry.stop_requested = True
            process = entry.process
        if process is None or process.poll() is not None:
            return
        _terminate_process(process)

    def _wait_or_force(self, entry: _BackgroundTaskEntry, grace_seconds: float) -> None:
        process = entry.process
        if process is None:
            return
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            _kill_process(process)
            with contextlib.suppress(Exception):
                process.wait(timeout=0.5)
        snapshot = entry.snapshot()
        if snapshot.status == "running" and snapshot.stop_requested and process.poll() is not None:
            self._settle(entry, "stopped", exit_code=process.returncode)

    def _prune_terminal_entries(self) -> None:
        with self._lock:
            terminal = [
                entry
                for entry in self._entries.values()
                if entry.status != "running"
            ]
            terminal.sort(key=lambda entry: (entry.end_time or entry.start_time, entry.start_time))
            while len(terminal) > self.max_terminal_tasks:
                oldest = terminal.pop(0)
                self._entries.pop(oldest.id, None)


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        with contextlib.suppress(OSError):
            process.terminate()
        return
    with contextlib.suppress(OSError, ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)


def _kill_process(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        with contextlib.suppress(OSError):
            process.kill()
        return
    with contextlib.suppress(OSError, ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
