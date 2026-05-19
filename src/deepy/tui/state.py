from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from deepy.usage import TokenUsage, normalize_usage


@dataclass(frozen=True)
class TuiState:
    busy: bool = False
    session_id: str | None = None
    status: str = "Idle"
    assistant_buffer: str = ""
    reasoning_buffer: str = ""
    pending_tool_calls: dict[str, str] = field(default_factory=dict)
    usage: TokenUsage = field(default_factory=TokenUsage)
    pending_questions: list[dict[str, Any]] = field(default_factory=list)
    quit_confirm_pending: bool = False
    interrupt_requested: bool = False


def set_busy(state: TuiState, busy: bool, status: str) -> TuiState:
    return replace(state, busy=busy, status=status, interrupt_requested=False if not busy else state.interrupt_requested)


def set_status(state: TuiState, status: str) -> TuiState:
    return replace(state, status=status)


def set_session_id(state: TuiState, session_id: str | None) -> TuiState:
    return replace(state, session_id=session_id)


def set_usage(state: TuiState, usage: Any) -> TuiState:
    return replace(state, usage=normalize_usage(usage))


def set_pending_questions(state: TuiState, questions: list[dict[str, Any]]) -> TuiState:
    return replace(state, pending_questions=questions)


def add_assistant_delta(state: TuiState, delta: str) -> TuiState:
    return replace(state, assistant_buffer=state.assistant_buffer + delta)


def add_reasoning_delta(state: TuiState, delta: str) -> TuiState:
    return replace(state, reasoning_buffer=state.reasoning_buffer + delta)


def reset_turn_buffers(state: TuiState) -> TuiState:
    return replace(state, assistant_buffer="", reasoning_buffer="")


def set_quit_confirm(state: TuiState, pending: bool) -> TuiState:
    return replace(state, quit_confirm_pending=pending)


def request_interrupt(state: TuiState) -> TuiState:
    return replace(state, interrupt_requested=True)
