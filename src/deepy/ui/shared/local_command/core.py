"""Shared types and low-level helpers for local (``!``) shell commands.

Both the POSIX runner (in :mod:`deepy.ui.shared.local_command`) and the Windows runner
(in :mod:`deepy.ui.shared.local_command.windows`) depend on this module, so it must not
import either of them.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepy.tools.shell_output import decode_shell_output_bytes
from deepy.tools.shell_utils import RuntimeEnvironment

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
        "command": result.command,
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
