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
            {"type": "raw_response_event", "data": type("Data", (), {"delta": "lo"})()},
        )()


@dataclass
class CapturedRun:
    agent_name: str
    input: str
    max_turns: int
    session_id: str


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
                )
            )
            assert run_config.trace_include_sensitive_data is False
            assert run_config.reasoning_item_id_policy == "omit"
            assert callable(run_config.session_input_callback)
            return FakeStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    emitted: list[str] = []

    summary = await run_prompt_once(
        "say hello",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        emit=emitted.append,
        max_turns=3,
    )

    assert summary.output == "hello"
    assert summary.complete is True
    assert emitted == ["hel", "lo"]
    assert captured == [
        CapturedRun(
            agent_name="Deepy",
            input="say hello",
            max_turns=3,
            session_id=summary.session_id,
        )
    ]
