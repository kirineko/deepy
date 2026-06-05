from __future__ import annotations

import contextlib
import os
import select
import threading
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

from deepy.background_tasks import BackgroundTaskManager
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.ui.classic.terminal_types import termios, tty
from deepy.ui.shared.render.styles import UiPalette


def _prompt_for_background_stop_selection(prompt: str) -> str:
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def _(event) -> None:  # pragma: no cover - prompt_toolkit calls this callback
        event.app.exit(result="")

    session: PromptSession[str] = PromptSession(key_bindings=bindings)
    try:
        return session.prompt(f"{prompt}: ").strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def _cleanup_background_tasks(
    console,
    background_tasks: BackgroundTaskManager,
    *,
    palette: UiPalette,
) -> None:
    running = background_tasks.running_count()
    if running == 0:
        return
    summary = background_tasks.stop_all(force_after_grace=True)
    count = len(summary.stopped)
    task_label = "task" if count == 1 else "tasks"
    console.print(f"[{palette.muted}]Stopped {count} background {task_label}.[/]")


@contextlib.contextmanager
def _esc_interrupt_watcher(
    interrupt_requested: threading.Event,
    *,
    suspend_event: threading.Event | None = None,
):
    if termios is not None and tty is not None and Path("/dev/tty").exists():
        target = _watch_posix_esc_keypress
    elif _resolve("msvcrt") is not None:
        target = _watch_windows_esc_keypress
    else:
        yield
        return

    stop_event = threading.Event()
    thread = threading.Thread(
        target=target,
        args=(interrupt_requested, stop_event, suspend_event),
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=0.2)


def _watch_posix_esc_keypress(
    interrupt_requested: threading.Event,
    stop_event: threading.Event,
    suspend_event: threading.Event | None = None,
) -> None:
    fd: int | None = None
    old_attrs: list | None = None
    try:
        if termios is None or tty is None:
            return
        fd = os.open("/dev/tty", os.O_RDONLY | os.O_NONBLOCK)
        old_attrs = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        while not stop_event.is_set() and not interrupt_requested.is_set():
            if suspend_event is not None and suspend_event.is_set():
                time.sleep(0.05)
                continue
            readable, _, _ = select.select([fd], [], [], 0.05)
            if not readable:
                continue
            try:
                data = os.read(fd, 32)
            except BlockingIOError:
                continue
            if b"\x1b" in data:
                interrupt_requested.set()
                return
    except Exception:
        return
    finally:
        if fd is not None:
            if old_attrs is not None:
                with contextlib.suppress(Exception):
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            with contextlib.suppress(Exception):
                os.close(fd)


def _watch_windows_esc_keypress(
    interrupt_requested: threading.Event,
    stop_event: threading.Event,
    suspend_event: threading.Event | None = None,
) -> None:
    if _resolve("msvcrt") is None:
        return
    kbhit = getattr(_resolve("msvcrt"), "kbhit", None)
    getwch = getattr(_resolve("msvcrt"), "getwch", None)
    if not callable(kbhit) or not callable(getwch):
        return
    while not stop_event.is_set() and not interrupt_requested.is_set():
        if suspend_event is not None and suspend_event.is_set():
            time.sleep(0.05)
            continue
        try:
            if not kbhit():
                time.sleep(0.05)
                continue
            key = getwch()
        except Exception:
            return
        if key == "\x1b":
            interrupt_requested.set()
            return
