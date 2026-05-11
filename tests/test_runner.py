from __future__ import annotations

from dataclasses import dataclass

import pytest
from agents import ModelSettings

from deepy.config import Settings
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
