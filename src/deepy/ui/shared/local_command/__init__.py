from __future__ import annotations

import contextlib
import errno
import os
import select
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from deepy.tools.result import ToolResult
from deepy.tools.shell_utils import RuntimeEnvironment, detect_runtime_environment
from deepy.utils import json as json_utils
from deepy.ui.shared.local_command.core import (
    DEFAULT_CONTEXT_OUTPUT_LIMIT,
    DEFAULT_DISPLAY_OUTPUT_LIMIT,
    DEFAULT_LOCAL_COMMAND_TIMEOUT_MS,
    LocalCommandInput,
    LocalCommandResult,
    _command_error,
    _decode_output,
    _elapsed_ms,
    _error_result,
    _limit_output,
    _resolve_shell_path,
    _sanitize_terminal_output,
    _shell_args,
    _shell_metadata,
    _terminate_process,
    _TRUNCATED_MARKER,
)
from deepy.ui.shared.local_command.windows import _read_pipe_output as _read_pipe_output
from deepy.ui.shared.local_command.windows import (
    _prepare_windows_process_env,
    _run_windows_pipes,
)

pty: Any | None
try:
    import pty as _pty
except ImportError:  # pragma: no cover - exercised on Windows.
    pty = None
else:
    pty = _pty


def parse_local_command(text: str) -> LocalCommandInput | None:
    stripped = text.strip()
    if not stripped.startswith("!"):
        return None
    return LocalCommandInput(raw_text=stripped, command=stripped[1:].strip())


def run_local_command(
    command: str,
    *,
    cwd: Path,
    timeout_ms: int = DEFAULT_LOCAL_COMMAND_TIMEOUT_MS,
    display_limit: int = DEFAULT_DISPLAY_OUTPUT_LIMIT,
    context_limit: int = DEFAULT_CONTEXT_OUTPUT_LIMIT,
    env: Mapping[str, str] | None = None,
    shell_path: str | None = None,
    platform_name: str | None = None,
    os_name: str | None = None,
    should_interrupt: Callable[[], bool] | None = None,
) -> LocalCommandResult:
    started_at = time.monotonic()
    process_env = dict(os.environ if env is None else env)
    resolved_shell = shell_path or _resolve_shell_path(process_env, os_name=os_name)
    runtime = detect_runtime_environment(
        shell_path=resolved_shell,
        env=process_env,
        platform_name=platform_name,
        os_name=os_name,
    )
    capture_limit = max(display_limit, context_limit) + len(_TRUNCATED_MARKER)

    if runtime.os_family == "windows":
        _prepare_windows_process_env(process_env)
        return _run_windows_pipes(
            command,
            cwd=cwd,
            env=process_env,
            runtime=runtime,
            shell_path=resolved_shell,
            timeout_ms=timeout_ms,
            display_limit=display_limit,
            context_limit=context_limit,
            capture_limit=capture_limit,
            started_at=started_at,
            should_interrupt=should_interrupt,
        )
    return _run_posix_pty(
        command,
        cwd=cwd,
        env=process_env,
        runtime=runtime,
        shell_path=resolved_shell,
        timeout_ms=timeout_ms,
        display_limit=display_limit,
        context_limit=context_limit,
        capture_limit=capture_limit,
        started_at=started_at,
        should_interrupt=should_interrupt,
    )


def build_synthetic_shell_transcript_items(
    raw_text: str,
    result: LocalCommandResult,
    *,
    call_id: str | None = None,
) -> list[dict[str, Any]]:
    resolved_call_id = call_id or f"call-deepy-local-{uuid.uuid4().hex}"
    arguments = json_utils.dumps({"command": result.command})
    return [
        {"role": "user", "content": raw_text},
        {
            "type": "function_call",
            "call_id": resolved_call_id,
            "name": "shell",
            "arguments": arguments,
        },
        {
            "type": "function_call_output",
            "call_id": resolved_call_id,
            "output": shell_tool_result_json(result, output=result.context_output),
        },
    ]


def shell_tool_result_json(
    result: LocalCommandResult,
    *,
    output: str | None = None,
) -> str:
    rendered_output = result.context_output if output is None else output
    if result.os_family == "windows":
        rendered_output = _sanitize_terminal_output(rendered_output)
    metadata = _shell_metadata(result)
    if result.ok:
        return ToolResult.ok_result("shell", rendered_output, metadata=metadata).to_json()
    return ToolResult.error_result(
        "shell",
        result.error or f"Command exited with code {result.exit_code}.",
        output=rendered_output,
        metadata=metadata,
    ).to_json()


def _run_posix_pty(
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
    if pty is None:
        return _error_result(
            command,
            cwd=cwd,
            runtime=runtime,
            shell_path=shell_path,
            timeout_ms=timeout_ms,
            started_at=started_at,
            tty_mode="unavailable",
            error="POSIX local command mode requires Python pty support.",
        )
    master_fd: int | None = None
    process: subprocess.Popen[bytes] | None = None
    timed_out = False
    interrupted = False
    captured = bytearray()
    capture_truncated = False
    try:
        master_fd, slave_fd = pty.openpty()
        os.set_blocking(master_fd, False)
        process = subprocess.Popen(
            [shell_path, *_shell_args(runtime, command)],
            cwd=str(cwd),
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave_fd)
        deadline = started_at + timeout_ms / 1000
        while True:
            if process.poll() is not None:
                _read_available(master_fd, captured, capture_limit)
                break
            if callable(should_interrupt) and should_interrupt():
                interrupted = True
                _terminate_process(process)
                _read_available(master_fd, captured, capture_limit)
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                _terminate_process(process)
                _read_available(master_fd, captured, capture_limit)
                break
            readable, _, _ = select.select([master_fd], [], [], min(0.05, remaining))
            if readable and _read_available(master_fd, captured, capture_limit):
                capture_truncated = True
        if len(captured) >= capture_limit:
            capture_truncated = True
        exit_code = process.poll()
        output = _decode_output(bytes(captured))
        error = _command_error(exit_code, timed_out=timed_out, interrupted=interrupted)
    except Exception as exc:
        exit_code = None
        output = ""
        error = str(exc)
    finally:
        if master_fd is not None:
            with contextlib.suppress(OSError):
                os.close(master_fd)

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
        tty_mode="pty",
        duration_ms=_elapsed_ms(started_at),
        timeout_ms=timeout_ms,
        timed_out=timed_out,
        interrupted=interrupted,
        display_output_truncated=display_truncated or capture_truncated,
        context_output_truncated=context_truncated or capture_truncated,
        capture_truncated=capture_truncated,
        error=error,
    )


def _read_available(master_fd: int, captured: bytearray, capture_limit: int) -> bool:
    truncated = False
    while True:
        try:
            chunk = os.read(master_fd, 4096)
        except BlockingIOError:
            return truncated
        except OSError as exc:
            if exc.errno == errno.EIO:
                return truncated
            raise
        if not chunk:
            return truncated
        if len(captured) < capture_limit:
            remaining = capture_limit - len(captured)
            captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True
        else:
            truncated = True
