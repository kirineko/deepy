from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from deepy.mcp import DeepyMcpRuntime, teardown_mcp_after_startup
from deepy.update_check import VersionUpdate


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
