from __future__ import annotations

from textual import events
from textual.containers import VerticalScroll
from textual.message import Message

from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary


class StreamEventMessage(Message):
    def __init__(self, event: DeepyStreamEvent) -> None:
        self.event = event
        super().__init__()


class TurnCompleteMessage(Message):
    def __init__(self, summary: RunSummary) -> None:
        self.summary = summary
        super().__init__()


class TurnFailedMessage(Message):
    def __init__(self, error: Exception) -> None:
        self.error = error
        super().__init__()


class TranscriptScroll(VerticalScroll):
    _WHEEL_SCROLL_LINES = 4

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.prevent_default()
        event.stop()
        self.scroll_relative(
            y=max(1, abs(event.delta_y)) * self._WHEEL_SCROLL_LINES,
            animate=False,
            force=True,
            immediate=True,
        )

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.prevent_default()
        event.stop()
        self.scroll_relative(
            y=-max(1, abs(event.delta_y)) * self._WHEEL_SCROLL_LINES,
            animate=False,
            force=True,
            immediate=True,
        )


