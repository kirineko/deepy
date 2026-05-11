from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from agents import ModelSettings

from deepy.config import Settings
from deepy.config.settings import LoggingConfig, NotifyConfig
from deepy.llm.provider import ProviderBundle
from deepy.llm.runner import run_prompt_once


class FakeStream:
    final_output = "hello"
    is_complete = True

    async def stream_events(self):
        yield type(
            "Event",
            (),
            {"type": "raw_response_event", "data": type("Data", (), {"delta": "hel"})()},
        )()
        yield type(
            "Event",
            (),
            {
                "type": "run_item_stream_event",
                "name": "tool_called",
                "item": type("Item", (), {"tool_name": "read", "call_id": "call-1"})(),
            },
        )()
        yield type(
            "Event",
            (),
            {"type": "raw_response_event", "data": type("Data", (), {"delta": "lo"})()},
        )()


class FailingStream:
    final_output = None
    is_complete = False

    async def stream_events(self):
        raise RuntimeError("provider failed api_key=sk-secret")
        yield


class CancellableStream:
    final_output = None
    is_complete = False

    def __init__(self):
        self.cancel_calls: list[str] = []

    async def stream_events(self):
        yield type(
            "Event",
            (),
            {"type": "raw_response_event", "data": type("Data", (), {"delta": "partial"})()},
        )()
        yield type(
            "Event",
            (),
            {"type": "raw_response_event", "data": type("Data", (), {"delta": "late"})()},
        )()

    def cancel(self, mode="immediate"):
        self.cancel_calls.append(mode)


class AskUserQuestionStream:
    final_output = None
    is_complete = False

    def __init__(self):
        self.cancel_calls: list[str] = []

    async def stream_events(self):
        yield type(
            "Event",
            (),
            {
                "type": "run_item_stream_event",
                "name": "tool_output",
                "item": type(
                    "Item",
                    (),
                    {
                        "tool_name": "AskUserQuestion",
                        "call_id": "call-1",
                        "output": json.dumps(
                            {
                                "ok": True,
                                "name": "AskUserQuestion",
                                "output": "Waiting for user input.",
                                "awaitUserResponse": True,
                                "metadata": {
                                    "kind": "ask_user_question",
                                    "questions": [
                                        {
                                            "question": "Continue?",
                                            "options": [{"label": "Yes"}, {"label": "No"}],
                                        }
                                    ],
                                },
                            }
                        ),
                    },
                )(),
            },
        )()
        yield type(
            "Event",
            (),
            {"type": "raw_response_event", "data": type("Data", (), {"delta": "late"})()},
        )()

    def cancel(self, mode="immediate"):
        self.cancel_calls.append(mode)


@dataclass
class CapturedRun:
    agent_name: str
    input: str
    max_turns: int
    session_id: str
    instructions: str = ""


@pytest.mark.asyncio
async def test_run_prompt_once_wires_agent_session_and_stream(monkeypatch, tmp_path):
    captured: list[CapturedRun] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            captured.append(
                CapturedRun(
                    agent_name=agent.name,
                    input=input,
                    max_turns=max_turns,
                    session_id=session.session_id,
                    instructions=agent.instructions,
                )
            )
            assert run_config.trace_include_sensitive_data is False
            assert run_config.reasoning_item_id_policy == "omit"
            assert callable(run_config.session_input_callback)
            return FakeStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    emitted: list[str] = []
    emitted_events: list[str] = []

    summary = await run_prompt_once(
        "say hello",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        emit=emitted.append,
        emit_event=lambda event: emitted_events.append(event.kind),
        max_turns=3,
    )

    assert summary.output == "hello"
    assert summary.complete is True
    assert emitted == ["hel", "lo"]
    assert emitted_events == ["text_delta", "tool_call", "text_delta"]
    assert captured == [
        CapturedRun(
            agent_name="Deepy",
            input="say hello",
            max_turns=3,
            session_id=summary.session_id,
            instructions=captured[0].instructions,
        )
    ]


@pytest.mark.asyncio
async def test_run_prompt_once_uses_requested_session(monkeypatch, tmp_path):
    captured_session_ids: list[str] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            captured_session_ids.append(session.session_id)
            return FakeStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "continue",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        session_id="known-session",
    )

    assert summary.session_id == "known-session"
    assert captured_session_ids == ["known-session"]


@pytest.mark.asyncio
async def test_run_prompt_once_loads_requested_skill(monkeypatch, tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\nUse this skill.",
        encoding="utf-8",
    )
    captured_instructions: list[str] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            captured_instructions.append(agent.instructions)
            return FakeStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    await run_prompt_once(
        "use a skill",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        skill_names=["demo"],
    )

    assert "Loaded skills:" in captured_instructions[0]
    assert "Use this skill." in captured_instructions[0]


@pytest.mark.asyncio
async def test_run_prompt_once_auto_loads_matching_skill(monkeypatch, tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "django"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: django\ndescription: Django migration specialist\n---\nUse Django skill.",
        encoding="utf-8",
    )
    captured_instructions: list[str] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            captured_instructions.append(agent.instructions)
            return FakeStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    await run_prompt_once(
        "fix the django migration",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert "Use Django skill." in captured_instructions[0]


@pytest.mark.asyncio
async def test_run_prompt_once_logs_debug_and_notifies(monkeypatch, tmp_path):
    debug_entries: list[dict] = []
    notify_calls: list[tuple[str, int, Path]] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return FakeStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    monkeypatch.setattr("deepy.llm.runner.log_debug_event", debug_entries.append)
    monkeypatch.setattr(
        "deepy.llm.runner.launch_notify_script",
        lambda command, duration_ms, root: notify_calls.append((command, duration_ms, root)),
    )

    summary = await run_prompt_once(
        "say hello",
        project_root=tmp_path,
        settings=Settings(
            logging=LoggingConfig(debug=True),
            notify=NotifyConfig(enabled=True, command="/tmp/notify.sh"),
        ),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.output == "hello"
    assert debug_entries[0]["request"] == {"input": "say hello", "max_turns": 10}
    assert debug_entries[0]["response"] == {"output": "hello"}
    assert notify_calls and notify_calls[0][0] == "/tmp/notify.sh"
    assert notify_calls[0][2] == tmp_path


@pytest.mark.asyncio
async def test_run_prompt_once_logs_api_error_before_reraising(monkeypatch, tmp_path):
    error_entries: list[dict] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return FailingStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    monkeypatch.setattr("deepy.llm.runner.log_api_error", error_entries.append)

    with pytest.raises(RuntimeError, match="provider failed"):
        await run_prompt_once(
            "explode",
            project_root=tmp_path,
            settings=Settings(),
            provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        )

    assert error_entries[0]["location"] == "deepy.llm.runner.run_prompt_once"
    assert error_entries[0]["request"] == {"input": "explode", "max_turns": 10}
    assert isinstance(error_entries[0]["error"], RuntimeError)


@pytest.mark.asyncio
async def test_run_prompt_once_cancels_stream_when_interrupted(monkeypatch, tmp_path):
    stream = CancellableStream()

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return stream

    monkeypatch.setattr("agents.Runner", FakeRunner)
    checks = iter([False, True])

    summary = await run_prompt_once(
        "stop soon",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        should_interrupt=lambda: next(checks),
        cancel_mode="after_turn",
    )

    assert summary.output == "partial"
    assert summary.complete is False
    assert summary.interrupted is True
    assert summary.status == "interrupted"
    assert stream.cancel_calls == ["after_turn"]


@pytest.mark.asyncio
async def test_run_prompt_once_stops_for_ask_user_question(monkeypatch, tmp_path):
    stream = AskUserQuestionStream()

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return stream

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "ask me",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.complete is False
    assert summary.status == "waiting_for_user"
    assert summary.pending_questions == [
        {"question": "Continue?", "options": [{"label": "Yes"}, {"label": "No"}]}
    ]
    assert stream.cancel_calls == ["after_turn"]
