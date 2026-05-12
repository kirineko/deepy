from __future__ import annotations

from deepy.sessions import SessionEntry
from deepy.llm.context import estimate_tokens_for_text
from deepy.ui.app import DeepyAppState
from deepy.ui.app import StreamProgress
from deepy.ui.app import append_message
from deepy.ui.app import clear_for_new_session
from deepy.ui.app import set_busy
from deepy.ui.app import set_error_line
from deepy.ui.app import set_pending_questions
from deepy.ui.app import set_running_processes
from deepy.ui.app import set_sessions
from deepy.ui.app import set_status_line
from deepy.ui.app import set_view
from deepy.ui.app import update_stream_progress
from deepy.ui.ask_user_question import AskUserQuestionItem, AskUserQuestionOption


def test_app_state_tracks_view_busy_messages_and_status():
    state = DeepyAppState()

    state = set_view(state, "sessions")
    state = set_busy(state, True, status_line="Thinking...")
    state = append_message(state, {"role": "user", "content": "hello"})
    state = set_error_line(state, "failed")
    state = set_status_line(state, "Ready")

    assert state.current_view == "sessions"
    assert state.busy is True
    assert state.messages == [{"role": "user", "content": "hello"}]
    assert state.status_line == "Ready"
    assert state.error_line == ""


def test_app_state_tracks_sessions_processes_and_progress():
    entry = SessionEntry("s1", "s1.jsonl", active_tokens=10, created_at=1, updated_at=2)
    state = set_sessions(DeepyAppState(), [entry])
    state = set_running_processes(state, {"123": {"command": "pytest"}})
    state = update_stream_progress(state, text_delta="hello", reasoning_delta="plan", tool_call=True)

    assert state.sessions == [entry]
    assert state.running_processes == {"123": {"command": "pytest"}}
    assert state.stream_progress == StreamProgress(
        text_tokens=estimate_tokens_for_text("hello"),
        reasoning_tokens=estimate_tokens_for_text("plan"),
        tool_calls=1,
    )


def test_app_state_tracks_pending_questions_and_new_session_reset():
    question = AskUserQuestionItem(
        question="Continue?",
        options=[AskUserQuestionOption(label="Yes")],
    )
    state = set_pending_questions(DeepyAppState(messages=[{"role": "assistant"}]), [question])

    assert state.current_view == "question"
    assert state.pending_questions == [question]

    reset = clear_for_new_session(state)

    assert reset.current_view == "chat"
    assert reset.messages == []
    assert reset.pending_questions == []
    assert reset.stream_progress == StreamProgress()
    assert reset.status_line == "Started a new session."
