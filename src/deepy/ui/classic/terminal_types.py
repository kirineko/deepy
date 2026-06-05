from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from deepy.llm.runner import RunSummary
from deepy.update_check import VersionUpdate

RunOnce = Callable[..., Coroutine[Any, Any, RunSummary]]
InputFunc = Callable[[str], str]
VersionUpdateChecker = Callable[[str], VersionUpdate | None]

MAX_CLARIFICATION_ROUNDS_PER_TURN = 5
RUNTIME_STATUS_REFRESH_SECONDS = 1.0
RUNTIME_STREAM_STATUS_UPDATE_SECONDS = 0.2

try:
    import termios as _termios
    import tty as _tty
except ImportError:  # pragma: no cover - exercised on Windows.
    termios: Any | None = None
    tty: Any | None = None
else:
    termios = _termios
    tty = _tty

msvcrt: Any | None
try:
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised on non-Windows platforms.
    msvcrt = None
else:
    msvcrt = _msvcrt
