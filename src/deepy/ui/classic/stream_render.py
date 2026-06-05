from __future__ import annotations

import threading
import time
from typing import Any

from rich.console import Console
from rich.text import Text

from deepy.format_tokens import format_stream_token_count_short as _format_stream_token_count_short
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.llm.events import DeepyStreamEvent
from deepy.ui.classic.printing import (
    _print_stream_event,
    _silent_generation_status_detail,
    _stream_event_writes_terminal,
)
from deepy.ui.classic.runtime_workers import ToolCallDisplay
from deepy.ui.classic.status.runtime_status import (
    _STATUS_SEPARATOR,
    _runtime_tool_activity_name,
    _working_status_text,
)
from deepy.ui.classic.terminal_types import (
    RUNTIME_STATUS_REFRESH_SECONDS,
    RUNTIME_STREAM_STATUS_UPDATE_SECONDS,
)
from deepy.ui.classic.status.status_footer import StatusFooter
from deepy.ui.shared.render.message_view import format_tool_display_label
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette


class TerminalStreamRenderer:
    def __init__(
        self,
        console: Console,
        *,
        project_root: str | None = None,
        status: Any | None = None,
        status_started_at: float | None = None,
        palette: UiPalette | None = None,
        footer: StatusFooter | None = None,
        output_lock: threading.RLock | None = None,
        view_mode: str = "concise",
        approved_preflight_diffs: set[str] | None = None,
    ) -> None:
        self.console = console
        self.project_root = project_root
        self.status = status
        self.palette = palette or DARK_PALETTE
        self.footer = footer
        self.status_started_at = (
            status_started_at if status_started_at is not None else time.monotonic()
        )
        self.status_detail = ""
        self.pending_tool_calls: dict[str, ToolCallDisplay] = {}
        self.reasoning_started = False
        self.reasoning_buffer = ""
        self.reasoning_updated_at = 0.0
        self.view_mode = view_mode if view_mode in {"concise", "full"} else "concise"
        self.stream_tokens = 0
        self.stream_status_updated_at = 0.0
        self.activity_state = ""
        self.output_lock = output_lock
        self.approved_preflight_diffs = approved_preflight_diffs

    def __call__(self, event: DeepyStreamEvent) -> None:
        if self.output_lock is None:
            self._record_stream_progress(event)
            if self._stream_event_writes_terminal(event):
                self._clear_status_for_output()
            self._update_status_for_silent_generation(event)
            _print_stream_event(
                self.console,
                event,
                project_root=self.project_root,
                pending_tool_calls=self.pending_tool_calls,
                reasoning_sink=self,
                palette=self.palette,
                approved_preflight_diffs=self.approved_preflight_diffs,
            )
            return
        with self.output_lock:
            self._record_stream_progress(event)
            if self._stream_event_writes_terminal(event):
                self._clear_status_for_output()
            self._update_status_for_silent_generation(event)
            _print_stream_event(
                self.console,
                event,
                project_root=self.project_root,
                pending_tool_calls=self.pending_tool_calls,
                reasoning_sink=self,
                palette=self.palette,
                approved_preflight_diffs=self.approved_preflight_diffs,
            )

    def add_reasoning(self, text: str) -> None:
        if not text:
            return
        self.activity_state = "Thinking"
        if self.view_mode == "concise":
            if self.status is not None:
                self.update_status(self._runtime_status_detail())
            return
        if not self.reasoning_started:
            self.console.print(
                Text.assemble(
                    ("• ", self.palette.muted),
                    (format_tool_display_label("Thinking"), f"bold {self.palette.muted}"),
                ),
            )
            self.reasoning_started = True
        self.reasoning_buffer = "printed"
        self.reasoning_updated_at = time.monotonic()
        self.console.print(Text(text, style=self.palette.muted), end="")
        if self.status is not None:
            self.update_status(self._runtime_status_detail())

    def set_tool_status(self, tool_name: str) -> None:
        self.activity_state = _runtime_tool_activity_name(tool_name)
        if self.status is not None and self.activity_state:
            self.update_status(self._runtime_status_detail())

    def update_status(self, detail: str | None = None) -> None:
        if detail is not None:
            self.status_detail = detail
        if self.status is not None and not self._status_output_is_blocked():
            if (
                self._status_detail_has_stream_tokens()
                and getattr(self.status, "inline_output_flow", False)
                and getattr(self.status, "active", False)
            ):
                now = time.monotonic()
                if now - self.stream_status_updated_at < RUNTIME_STREAM_STATUS_UPDATE_SECONDS:
                    return
                self.stream_status_updated_at = now
            self.status.update(
                _working_status_text(
                    self.status_started_at,
                    self.status_detail,
                    palette=self.palette,
                    footer=self.footer,
                )
            )

    def refresh_status(self) -> None:
        if self.output_lock is not None:
            with self.output_lock:
                self.update_status()
            return
        self.update_status()

    def _clear_status_for_output(self) -> None:
        clear_for_output = getattr(self.status, "clear_for_output", None)
        if callable(clear_for_output):
            clear_for_output()

    def _status_output_is_blocked(self) -> bool:
        if not (self.reasoning_buffer and getattr(self.status, "inline_output_flow", False)):
            return False
        if time.monotonic() - self.reasoning_updated_at < RUNTIME_STATUS_REFRESH_SECONDS:
            return True
        self._flush_unlocked()
        return False

    def _update_status_for_silent_generation(self, event: DeepyStreamEvent) -> None:
        detail = _silent_generation_status_detail(event)
        if self.status is None or detail is None:
            return
        if detail == "":
            if event.kind in {"text_delta", "message"}:
                self.activity_state = "Responding"
            detail = self._runtime_status_detail()
        if self.reasoning_buffer:
            self._flush_unlocked()
        if self.status_detail == detail and getattr(self.status, "active", False):
            return
        self.update_status(detail)

    def _record_stream_progress(self, event: DeepyStreamEvent) -> None:
        if event.kind not in {"reasoning_delta", "text_delta", "raw_response"} or not event.text:
            return
        self.stream_tokens += _resolve("estimate_tokens_for_text")(event.text)

    def _stream_status_detail(self) -> str | None:
        if self.stream_tokens <= 0:
            return None
        return f"↓ {_format_stream_token_count_short(self.stream_tokens)} tokens"

    def _runtime_status_detail(self) -> str:
        parts: list[str] = []
        stream_detail = self._stream_status_detail()
        if stream_detail:
            parts.append(stream_detail)
        if self.activity_state:
            parts.append(self.activity_state)
        return _STATUS_SEPARATOR.join(parts)

    def _status_detail_has_stream_tokens(self) -> bool:
        return self.status_detail == "↓ " or self.status_detail.startswith("↓ ")

    def flush(self) -> None:
        if self.output_lock is not None:
            with self.output_lock:
                self._flush_unlocked()
            return
        self._flush_unlocked()

    def _flush_unlocked(self) -> None:
        if self.reasoning_buffer:
            self.console.print()
        self.reasoning_started = False
        self.reasoning_buffer = ""

    def _stream_event_writes_terminal(self, event: DeepyStreamEvent) -> bool:
        if event.kind == "reasoning_delta" and self.view_mode == "concise":
            return False
        return _stream_event_writes_terminal(event)

