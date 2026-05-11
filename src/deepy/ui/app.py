from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from deepy.sessions import SessionEntry
from deepy.skills import SkillInfo
from deepy.ui.ask_user_question import AskUserQuestionItem


AppView = Literal["chat", "sessions", "skills", "status", "question"]


@dataclass(frozen=True)
class StreamProgress:
    text_tokens: int = 0
    reasoning_tokens: int = 0
    tool_calls: int = 0


@dataclass(frozen=True)
class DeepyAppState:
    current_view: AppView = "chat"
    busy: bool = False
    messages: list[dict[str, Any]] = field(default_factory=list)
    sessions: list[SessionEntry] = field(default_factory=list)
    skills: list[SkillInfo] = field(default_factory=list)
    status_line: str = ""
    error_line: str = ""
    stream_progress: StreamProgress = field(default_factory=StreamProgress)
    running_processes: dict[str, dict[str, str]] = field(default_factory=dict)
    pending_questions: list[AskUserQuestionItem] = field(default_factory=list)


def set_view(state: DeepyAppState, view: AppView) -> DeepyAppState:
    return replace(state, current_view=view)


def set_busy(state: DeepyAppState, busy: bool, *, status_line: str = "") -> DeepyAppState:
    return replace(state, busy=busy, status_line=status_line)


def append_message(state: DeepyAppState, message: dict[str, Any]) -> DeepyAppState:
    return replace(state, messages=[*state.messages, message])


def set_sessions(state: DeepyAppState, sessions: list[SessionEntry]) -> DeepyAppState:
    return replace(state, sessions=list(sessions))


def set_skills(state: DeepyAppState, skills: list[SkillInfo]) -> DeepyAppState:
    return replace(state, skills=list(skills))


def set_status_line(state: DeepyAppState, status_line: str) -> DeepyAppState:
    return replace(state, status_line=status_line, error_line="")


def set_error_line(state: DeepyAppState, error_line: str) -> DeepyAppState:
    return replace(state, error_line=error_line)


def update_stream_progress(
    state: DeepyAppState,
    *,
    text_delta: str = "",
    reasoning_delta: str = "",
    tool_call: bool = False,
) -> DeepyAppState:
    progress = state.stream_progress
    return replace(
        state,
        stream_progress=StreamProgress(
            text_tokens=progress.text_tokens + _estimate_tokens(text_delta),
            reasoning_tokens=progress.reasoning_tokens + _estimate_tokens(reasoning_delta),
            tool_calls=progress.tool_calls + (1 if tool_call else 0),
        ),
    )


def set_running_processes(
    state: DeepyAppState,
    running_processes: dict[str, dict[str, str]],
) -> DeepyAppState:
    return replace(
        state,
        running_processes={pid: dict(value) for pid, value in running_processes.items()},
    )


def set_pending_questions(
    state: DeepyAppState,
    pending_questions: list[AskUserQuestionItem],
) -> DeepyAppState:
    return replace(
        state,
        current_view="question" if pending_questions else state.current_view,
        pending_questions=list(pending_questions),
    )


def clear_for_new_session(state: DeepyAppState) -> DeepyAppState:
    return replace(
        state,
        current_view="chat",
        busy=False,
        messages=[],
        status_line="Started a new session.",
        error_line="",
        stream_progress=StreamProgress(),
        running_processes={},
        pending_questions=[],
    )


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)
