from __future__ import annotations

import contextlib
import shutil
import threading
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.text import Text

from deepy.ui.classic.status.runtime_status import _fit_status_line, _style_runtime_status_line
from deepy.ui.classic.terminal_types import RUNTIME_STATUS_REFRESH_SECONDS
from deepy.ui.shared.render.styles import UiPalette

if TYPE_CHECKING:
    from deepy.ui.classic.stream_render import TerminalStreamRenderer


def _terminal_columns(console: Console) -> int:
    fallback = (max(1, console.width), 24)
    return max(1, shutil.get_terminal_size(fallback).columns)


def _refresh_working_status(
    renderer: TerminalStreamRenderer,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(RUNTIME_STATUS_REFRESH_SECONDS):
        renderer.refresh_status()


@contextlib.contextmanager
def _status_display(
    console: Console,
    initial_status: Text,
    *,
    palette: UiPalette,
):
    if _should_use_inline_runtime_status(console):
        output_lock = threading.RLock()
        status = _InlineRuntimeStatus(console, palette=palette, output_lock=output_lock)
        status.update(initial_status)
        try:
            yield status
        finally:
            status.clear()
        return

    yield _SilentStatus()


@contextlib.contextmanager
def _phase_status_display(
    console: Console,
    status_text: Text,
    *,
    palette: UiPalette,
):
    if not _should_use_inline_runtime_status(console):
        yield _SilentStatus()
        return
    status = _InlineRuntimeStatus(console, palette=palette)
    status.update(status_text)
    try:
        yield status
    finally:
        status.clear()


def _should_use_inline_runtime_status(console: Console) -> bool:
    isatty = getattr(console.file, "isatty", None)
    return bool(callable(isatty) and isatty())


class _InlineRuntimeStatus:
    inline_output_flow = True
    periodic_refresh = True

    def __init__(
        self,
        console: Console,
        *,
        palette: UiPalette,
        output_lock: Any | None = None,
    ) -> None:
        self.console = console
        self.palette = palette
        self.columns = 0
        self.output_lock = output_lock or threading.RLock()
        self.active = False

    def update(self, status: Text) -> None:
        with self.output_lock:
            columns = _terminal_columns(self.console)
            self.columns = columns
            self._write_line(status.plain)
            self.console.file.flush()

    def clear(self) -> None:
        with self.output_lock:
            if not self.active:
                return
            self.console.file.write("\r\x1b[2K")
            self.active = False
            self.console.file.flush()

    def clear_for_output(self) -> None:
        self.clear()

    def _write_line(self, text: str) -> None:
        width = max(self.columns - 1, 1)
        padded = _fit_status_line(text, width=width)
        self.console.file.write("\r\x1b[2K")
        self.console.print(_style_runtime_status_line(padded, self.palette), end="")
        self.active = True


class _SilentStatus:
    def update(self, status: Text) -> None:
        return None

