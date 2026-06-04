"""Windows pipe-based runner for local (``!``) shell commands.

Imports only :mod:`deepy.ui.shared.local_command.core` so it stays free of the dispatch
module that re-exports it.
"""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from deepy.tools.shell_utils import RuntimeEnvironment
from deepy.ui.shared.local_command.core import (
    LocalCommandResult,
    _command_error,
    _decode_output,
    _elapsed_ms,
    _limit_output,
    _sanitize_terminal_output,
    _shell_args,
    _terminate_windows_process,
)


def _run_windows_pipes(
    command: str,
    *,
    cwd: Path,
    env: dict[str, str],
    runtime: RuntimeEnvironment,
    shell_path: str,
    timeout_ms: int,
    display_limit: int,
    context_limit: int,
    capture_limit: int,
    started_at: float,
    should_interrupt: Callable[[], bool] | None,
) -> LocalCommandResult:
    process: subprocess.Popen[bytes] | None = None
    timed_out = False
    interrupted = False
    captured = bytearray()
    capture_truncated = False
    output_queue: queue.Queue[bytes] = queue.Queue()
    try:
        process = subprocess.Popen(
            [shell_path, *_shell_args(runtime, command)],
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        reader = threading.Thread(target=_read_pipe_output, args=(process, output_queue), daemon=True)
        reader.start()
        deadline = started_at + timeout_ms / 1000
        while True:
            drained_truncated = _drain_bytes_queue(
                output_queue,
                captured,
                capture_limit,
            )
            capture_truncated = capture_truncated or drained_truncated
            if process.poll() is not None:
                break
            if callable(should_interrupt) and should_interrupt():
                interrupted = True
                _terminate_windows_process(process)
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                _terminate_windows_process(process)
                break
            time.sleep(min(0.05, remaining))
        reader.join(timeout=0.2)
        capture_truncated = (
            capture_truncated or _drain_bytes_queue(output_queue, captured, capture_limit)
        )
        if len(captured) >= capture_limit:
            capture_truncated = True
        exit_code = process.poll()
        output = _sanitize_terminal_output(_decode_output(bytes(captured), windows_compatible=True))
        error = _command_error(exit_code, timed_out=timed_out, interrupted=interrupted)
    except Exception as exc:
        exit_code = None
        output = _sanitize_terminal_output(_decode_output(bytes(captured), windows_compatible=True))
        error = str(exc)

    display_output, display_truncated = _limit_output(output, display_limit)
    context_output, context_truncated = _limit_output(output, context_limit)
    return LocalCommandResult(
        command=command,
        output=output,
        display_output=display_output,
        context_output=context_output,
        exit_code=exit_code,
        cwd=cwd,
        shell_path=shell_path,
        shell_kind=runtime.shell_kind,
        command_dialect=runtime.command_dialect,
        path_style=runtime.path_style,
        os_family=runtime.os_family,
        tty_mode="pipe",
        duration_ms=_elapsed_ms(started_at),
        timeout_ms=timeout_ms,
        timed_out=timed_out,
        interrupted=interrupted,
        display_output_truncated=display_truncated or capture_truncated,
        context_output_truncated=context_truncated or capture_truncated,
        capture_truncated=capture_truncated,
        error=error,
    )


def _read_pipe_output(
    process: subprocess.Popen[bytes],
    output_queue: queue.Queue[bytes],
) -> None:
    stream = process.stdout
    if stream is None:
        return
    read1 = getattr(stream, "read1", None)
    if not callable(read1):
        return
    while True:
        try:
            chunk = read1(4096)
        except Exception:
            return
        if not chunk:
            return
        output_queue.put(chunk)


def _drain_bytes_queue(
    output_queue: queue.Queue[bytes],
    captured: bytearray,
    capture_limit: int,
) -> bool:
    truncated = False
    while True:
        try:
            chunk = output_queue.get_nowait()
        except queue.Empty:
            return truncated
        if len(captured) < capture_limit:
            remaining = capture_limit - len(captured)
            captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True
        else:
            truncated = True


def _prepare_windows_process_env(env: dict[str, str]) -> None:
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
