from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


Spawn = Callable[..., Any]


def format_duration_seconds(duration_ms: float | int) -> str:
    try:
        safe_ms = max(float(duration_ms), 0)
    except (TypeError, ValueError):
        safe_ms = 0
    return str(int(safe_ms // 1000))


def build_notify_env(
    duration_ms: float | int,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env["DURATION"] = format_duration_seconds(duration_ms)
    return env


def launch_notify_script(
    notify_path: str | None,
    duration_ms: float | int,
    working_directory: str | Path | None = None,
    *,
    spawn_process: Spawn | None = None,
) -> None:
    command_path = (notify_path or "").strip()
    if not command_path:
        return

    cwd = str(working_directory) if working_directory is not None else None
    env = build_notify_env(duration_ms)
    spawn = spawn_process or subprocess.Popen
    options = {
        "cwd": cwd,
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "start_new_session": os.name != "nt",
    }
    try:
        spawn([command_path], **options)
    except OSError as exc:
        if os.name == "nt" or exc.errno not in {8, 13}:
            return
        _spawn_fallback_shell(spawn, command_path, options)
    except Exception:
        return


def _spawn_fallback_shell(spawn: Spawn, command_path: str, options: dict[str, Any]) -> None:
    try:
        spawn(["/bin/sh", command_path], **options)
    except Exception:
        return
