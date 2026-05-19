from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from deepy.config import Settings
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


@dataclass
class TuiController:
    settings: Settings
    loaded_skill_names: list[str] = field(default_factory=list)
    prompt_history: list[str] = field(default_factory=list)
    prompt_history_index: int | None = None
    prompt_history_draft: str = ""

    def add_prompt_history(self, prompt: str) -> None:
        text = prompt.strip()
        if not text:
            return
        if not self.prompt_history or self.prompt_history[-1] != text:
            self.prompt_history.append(text)
        self.prompt_history_index = None
        self.prompt_history_draft = ""

    def previous_prompt(self, current: str) -> str | None:
        if not self.prompt_history:
            return None
        if self.prompt_history_index is None:
            self.prompt_history_draft = current
            self.prompt_history_index = len(self.prompt_history) - 1
        else:
            self.prompt_history_index = max(0, self.prompt_history_index - 1)
        return self.prompt_history[self.prompt_history_index]

    def next_prompt(self) -> str | None:
        if self.prompt_history_index is None:
            return None
        self.prompt_history_index += 1
        if self.prompt_history_index >= len(self.prompt_history):
            self.prompt_history_index = None
            return self.prompt_history_draft
        return self.prompt_history[self.prompt_history_index]

    def reset_session_state(self) -> None:
        self.loaded_skill_names.clear()


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
