from __future__ import annotations

import errno
import contextlib
import os
import queue
import re
import select
import shutil
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepy.tools.result import ToolResult
from deepy.tools.shell_output import decode_shell_output_bytes
from deepy.tools.shell_utils import RuntimeEnvironment, detect_runtime_environment
from deepy.utils import json as json_utils

pty: Any | None
try:
    import pty as _pty
except ImportError:  # pragma: no cover - exercised on Windows.
    pty = None
else:
    pty = _pty

DEFAULT_LOCAL_COMMAND_TIMEOUT_MS = 120_000
DEFAULT_DISPLAY_OUTPUT_LIMIT = 30_000
DEFAULT_CONTEXT_OUTPUT_LIMIT = 8_000
_TRUNCATED_MARKER = "\n... output truncated ...\n"
_ANSI_CONTROL_RE = re.compile(
    r"""
    \x1b
    (?:
        \[[0-?]*[ -/]*[@-~]
        |\][^\x07\x1b]*(?:\x07|\x1b\\)
        |P[^\x1b]*(?:\x1b\\)
        |_[^\x1b]*(?:\x1b\\)
        |\^[^\x1b]*(?:\x1b\\)
        |[@-Z\\-_]
    )
    """,
    re.VERBOSE,
)
_TERMINAL_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


@dataclass(frozen=True)
class LocalCommandInput:
    raw_text: str
    command: str


@dataclass(frozen=True)
class LocalCommandResult:
    command: str
    output: str
    display_output: str
    context_output: str
    exit_code: int | None
    cwd: Path
    shell_path: str
    shell_kind: str
    command_dialect: str
    path_style: str
    os_family: str
    tty_mode: str
    duration_ms: int
    timeout_ms: int
    timed_out: bool = False
    interrupted: bool = False
    display_output_truncated: bool = False
    context_output_truncated: bool = False
    capture_truncated: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.exit_code == 0 and not self.timed_out and not self.interrupted


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


def _shell_args(runtime: RuntimeEnvironment, command: str) -> list[str]:
    if runtime.command_dialect == "powershell":
        return ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command]
    if runtime.command_dialect == "cmd":
        return ["/d", "/s", "/c", command]
    return ["-c", command]


def _resolve_shell_path(env: Mapping[str, str], *, os_name: str | None = None) -> str:
    shell = env.get("SHELL")
    if shell:
        return shell
    if (os_name or os.name) == "nt":
        if "PSModulePath" in env:
            return (
                env.get("POWERSHELL")
                or shutil.which("pwsh")
                or shutil.which("powershell")
                or "powershell.exe"
            )
        return env.get("COMSPEC") or env.get("ComSpec") or "cmd.exe"
    return "/bin/zsh" if Path("/bin/zsh").exists() else "/bin/sh"


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            process.wait(timeout=0.2)


def _terminate_windows_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    with contextlib.suppress(OSError):
        process.terminate()
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            process.kill()
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            process.wait(timeout=0.2)


def _limit_output(output: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return (_TRUNCATED_MARKER if output else ""), bool(output)
    if len(output) <= limit:
        return output, False
    marker = _TRUNCATED_MARKER
    if limit <= len(marker):
        return output[:limit], True
    keep = max(0, limit - len(marker))
    return output[:keep] + marker, True


def _decode_output(output: bytes, *, windows_compatible: bool = False) -> str:
    if windows_compatible:
        text, _ = decode_shell_output_bytes(output)
    else:
        text = output.decode("utf-8", errors="replace")
    return _normalize_line_endings(text)


def _prepare_windows_process_env(env: dict[str, str]) -> None:
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")


def _sanitize_terminal_output(output: str) -> str:
    normalized = _normalize_line_endings(output)
    return _TERMINAL_CONTROL_CHAR_RE.sub("", _ANSI_CONTROL_RE.sub("", normalized))


def _normalize_line_endings(output: str) -> str:
    return output.replace("\r\n", "\n").replace("\r", "\n")


def _command_error(exit_code: int | None, *, timed_out: bool, interrupted: bool) -> str | None:
    if interrupted:
        return "Command interrupted."
    if timed_out:
        return "Command timed out."
    if exit_code is None or exit_code == 0:
        return None
    return f"Command exited with code {exit_code}."


def _shell_metadata(result: LocalCommandResult) -> dict[str, Any]:
    return {
        "cwd": str(result.cwd),
        "shellPath": result.shell_path,
        "shellKind": result.shell_kind,
        "commandDialect": result.command_dialect,
        "pathStyle": result.path_style,
        "osFamily": result.os_family,
        "ttyMode": result.tty_mode,
        "localCommandMode": True,
        "exitCode": result.exit_code,
        "durationMs": result.duration_ms,
        "timeoutMs": result.timeout_ms,
        "timedOut": result.timed_out,
        "interrupted": result.interrupted,
        "displayOutputTruncated": result.display_output_truncated,
        "contextOutputTruncated": result.context_output_truncated,
        "captureTruncated": result.capture_truncated,
        "contextOutputChars": len(result.context_output),
    }


def _error_result(
    command: str,
    *,
    cwd: Path,
    runtime: RuntimeEnvironment,
    shell_path: str,
    timeout_ms: int,
    started_at: float,
    tty_mode: str,
    error: str,
) -> LocalCommandResult:
    return LocalCommandResult(
        command=command,
        output="",
        display_output="",
        context_output="",
        exit_code=None,
        cwd=cwd,
        shell_path=shell_path,
        shell_kind=runtime.shell_kind,
        command_dialect=runtime.command_dialect,
        path_style=runtime.path_style,
        os_family=runtime.os_family,
        tty_mode=tty_mode,
        duration_ms=_elapsed_ms(started_at),
        timeout_ms=timeout_ms,
        error=error,
    )


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((time.monotonic() - started_at) * 1000))
