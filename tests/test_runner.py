from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from agents import ModelSettings
from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError
from openai import APIStatusError, BadRequestError

from deepy.config import ContextConfig, Settings
from deepy.config.settings import LoggingConfig, NotifyConfig
from deepy.llm.compaction import ContextCompactionError, ContextReadiness
from deepy.llm.provider import ProviderBundle
from deepy.llm.runner import DEFAULT_MAX_TURNS, format_deepseek_api_error, run_prompt_once
from deepy.sessions import DeepyJsonlSession


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


class UsageStream:
    final_output = "ok"
    is_complete = True

    async def stream_events(self):
        usage = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=2,
            total_tokens=12,
            completion_tokens_details={"reasoning_tokens": 1},
        )
        response = SimpleNamespace(usage=usage)
        yield type(
            "Event",
            (),
            {
                "type": "raw_response_event",
                "data": type(
                    "Data",
                    (),
                    {"type": "response.completed", "response": response},
                )(),
            },
        )()


class MultiUsageStream:
    final_output = "ok"
    is_complete = True

    async def stream_events(self):
        for usage in (
            SimpleNamespace(prompt_tokens=4, completion_tokens=1, total_tokens=5),
            SimpleNamespace(prompt_tokens=6, completion_tokens=2, total_tokens=8),
        ):
            response = SimpleNamespace(usage=usage)
            yield type(
                "Event",
                (),
                {
                    "type": "raw_response_event",
                    "data": type(
                        "Data",
                        (),
                        {"type": "response.completed", "response": response},
                    )(),
                },
            )()


class ContextUsageStream:
    final_output = "ok"
    is_complete = True
    context_wrapper = SimpleNamespace(
        usage=SimpleNamespace(
            requests=2,
            input_tokens=30,
            output_tokens=7,
            total_tokens=37,
            request_usage_entries=[
                SimpleNamespace(input_tokens=10, output_tokens=2, total_tokens=12),
                SimpleNamespace(input_tokens=20, output_tokens=5, total_tokens=25),
            ],
        )
    )

    async def stream_events(self):
        if False:
            yield None


class FailingStream:
    final_output = None
    is_complete = False

    async def stream_events(self):
        raise RuntimeError("provider failed api_key=sk-secret")
        yield


class DeepSeekStatusErrorStream:
    final_output = None
    is_complete = False

    async def stream_events(self):
        response = httpx.Response(
            402,
            request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
            json={
                "error": {
                    "message": "Insufficient Balance",
                    "type": "invalid_request_error",
                    "code": "invalid_request_error",
                }
            },
        )
        raise APIStatusError(
            "Error code: 402 - Insufficient Balance",
            response=response,
            body=response.json(),
        )
        yield


class ModelBehaviorErrorStream:
    final_output = None
    is_complete = False

    async def stream_events(self):
        raise ModelBehaviorError("Tool mcp_tavily__tavily_search not found in agent Deepy")
        yield


class MaxTurnsStream:
    final_output = None
    is_complete = False

    async def stream_events(self):
        yield type(
            "Event",
            (),
            {"type": "raw_response_event", "data": type("Data", (), {"delta": "partial"})()},
        )()
        raise MaxTurnsExceeded("Max turns exceeded")


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


class IdleCancellableStream:
    final_output = None
    is_complete = False

    def __init__(self):
        self.cancel_calls: list[str] = []
        self.cancelled = asyncio.Event()

    async def stream_events(self):
        await self.cancelled.wait()
        self.is_complete = True
        if False:
            yield None

    def cancel(self, mode="immediate"):
        self.cancel_calls.append(mode)
        self.cancelled.set()


class PersistingIdleCancellableStream:
    final_output = None
    is_complete = False

    def __init__(self, session, items: list[dict[str, object]]):
        self.session = session
        self.items = items
        self.cancel_calls: list[str] = []
        self.cancelled = asyncio.Event()

    async def stream_events(self):
        await self.session.add_items(self.items)
        await self.cancelled.wait()
        self.is_complete = True
        if False:
            yield None

    def cancel(self, mode="immediate"):
        self.cancel_calls.append(mode)
        self.cancelled.set()


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
async def test_run_prompt_once_session_input_callback_does_not_trim(monkeypatch, tmp_path):
    prepared_inputs: list[list[dict[str, object]]] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            history = [{"role": "user", "content": "old " * 1000}]
            new_input = [{"role": "user", "content": "current"}]
            prepared_inputs.append(run_config.session_input_callback(history, new_input))
            return FakeStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    await run_prompt_once(
        "say hello",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(
                window_tokens=10_000,
                compact_trigger_ratio=0.5,
                reserved_context_tokens=100,
            )
        ),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    prepared = prepared_inputs[0]
    assert prepared == [
        {"role": "user", "content": "old " * 1000},
        {"role": "user", "content": "current"},
    ]


@pytest.mark.asyncio
async def test_run_prompt_once_runs_auto_compaction_before_model_call(monkeypatch, tmp_path):
    calls: list[str] = []
    emitted: list[str] = []

    async def fake_ensure_context_ready(session, settings, *, provider=None, additional_input=None):
        calls.append(additional_input)
        return ContextReadiness(
            session_id=session.session_id,
            before_tokens=900,
            after_tokens=200,
            compacted=True,
        )

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            calls.append("model")
            return FakeStream()

    monkeypatch.setattr("deepy.llm.runner.ensure_context_ready", fake_ensure_context_ready)
    monkeypatch.setattr("agents.Runner", FakeRunner)

    await run_prompt_once(
        "continue",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        emit_event=lambda event: emitted.append(event.text) if event.kind == "status" else None,
    )

    assert calls == ["continue", "model"]
    assert emitted == ["Auto-compacted context 900 -> 200 tokens"]


@pytest.mark.asyncio
async def test_run_prompt_once_blocks_when_pre_run_compaction_fails(monkeypatch, tmp_path):
    async def fake_ensure_context_ready(session, settings, *, provider=None, additional_input=None):
        raise ContextCompactionError("too large")

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            raise AssertionError("model request should be blocked")

    monkeypatch.setattr("deepy.llm.runner.ensure_context_ready", fake_ensure_context_ready)
    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "continue",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.status == "context_compaction_failed"
    assert "too large" in summary.output


@pytest.mark.asyncio
async def test_run_prompt_once_uses_requested_session(monkeypatch, tmp_path):
    captured_session_ids: list[str] = []
    captured_inputs: list[object] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            captured_session_ids.append(session.session_id)
            captured_inputs.append(input)
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
    assert captured_inputs == ["continue"]


@pytest.mark.asyncio
async def test_run_prompt_once_returns_and_records_usage(monkeypatch, tmp_path):
    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return UsageStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "usage",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.usage.prompt_tokens == 10
    assert summary.usage.completion_tokens == 2
    assert summary.usage.reasoning_tokens == 1


@pytest.mark.asyncio
async def test_run_prompt_once_accumulates_multiple_stream_usage_events(monkeypatch, tmp_path):
    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return MultiUsageStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "usage",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.usage.prompt_tokens == 10
    assert summary.usage.completion_tokens == 3
    assert summary.usage.total_tokens == 13


@pytest.mark.asyncio
async def test_run_prompt_once_uses_sdk_accumulated_usage_for_multiple_requests(
    monkeypatch,
    tmp_path,
):
    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return ContextUsageStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "usage",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.usage.requests == 2
    assert summary.usage.prompt_tokens == 30
    assert summary.usage.completion_tokens == 7
    assert summary.usage.total_tokens == 37
    assert len(summary.usage.request_usage_entries) == 2


@pytest.mark.asyncio
async def test_run_prompt_once_loads_requested_skill(monkeypatch, tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
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
async def test_run_prompt_once_does_not_auto_load_matching_skill(monkeypatch, tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "django"
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

    assert "django - Django migration specialist" in captured_instructions[0]
    assert "Use Django skill." not in captured_instructions[0]


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
    assert debug_entries[0]["request"] == {
        "input": "say hello",
        "max_turns": DEFAULT_MAX_TURNS,
    }
    assert debug_entries[0]["response"] == {"output": "hello", "usage": {}}
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
    assert error_entries[0]["request"] == {
        "input": "explode",
        "max_turns": DEFAULT_MAX_TURNS,
    }
    assert isinstance(error_entries[0]["error"], RuntimeError)


@pytest.mark.asyncio
async def test_run_prompt_once_returns_deepseek_status_error_as_content(monkeypatch, tmp_path):
    error_entries: list[dict] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return DeepSeekStatusErrorStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    monkeypatch.setattr("deepy.llm.runner.log_api_error", error_entries.append)

    summary = await run_prompt_once(
        "explode",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.complete is False
    assert summary.status == "api_error"
    assert "DeepSeek API error 402: 余额不足" in summary.output
    assert "Server message: Insufficient Balance" in summary.output
    assert "Reason: 账号余额不足。" in summary.output
    assert "Suggestion: 请确认账户余额" in summary.output
    assert "code=invalid_request_error" in summary.output
    assert error_entries[0]["response"]["statusCode"] == 402
    assert error_entries[0]["response"]["body"]["error"]["message"] == "Insufficient Balance"


@pytest.mark.asyncio
async def test_run_prompt_once_returns_model_behavior_error_as_content(monkeypatch, tmp_path):
    error_entries: list[dict] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return ModelBehaviorErrorStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    monkeypatch.setattr("deepy.llm.runner.log_api_error", error_entries.append)

    summary = await run_prompt_once(
        "search",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
    )

    assert summary.complete is False
    assert summary.status == "agent_error"
    assert "Tool mcp_tavily__tavily_search not found in agent Deepy" in summary.output
    assert isinstance(error_entries[0]["error"], ModelBehaviorError)


def test_format_deepseek_api_error_includes_known_error_code_guidance():
    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
        json={"error": {"message": "bad request body", "type": "invalid_request_error"}},
    )
    error = BadRequestError(
        "Error code: 400 - bad request body",
        response=response,
        body=response.json(),
    )

    output = format_deepseek_api_error(error)

    assert "DeepSeek API error 400: 格式错误" in output
    assert "Server message: bad request body" in output
    assert "Reason: 请求体格式错误。" in output
    assert "Suggestion: 请根据错误信息提示修改请求体。" in output


@pytest.mark.asyncio
async def test_run_prompt_once_returns_summary_when_max_turns_exceeded(monkeypatch, tmp_path):
    error_entries: list[dict] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return MaxTurnsStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    monkeypatch.setattr("deepy.llm.runner.log_api_error", error_entries.append)

    summary = await run_prompt_once(
        "keep going",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        max_turns=5,
    )

    assert summary.complete is False
    assert summary.status == "max_turns_exceeded"
    assert "partial" in summary.output
    assert "max turn limit (5)" in summary.output
    assert summary.session_id
    assert error_entries == []


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
async def test_run_prompt_once_interrupt_watcher_cancels_idle_stream(monkeypatch, tmp_path):
    stream = IdleCancellableStream()

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            return stream

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "stop now",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        should_interrupt=lambda: True,
    )

    assert summary.output == ""
    assert summary.complete is False
    assert summary.interrupted is True
    assert summary.status == "interrupted"
    assert stream.cancel_calls == ["immediate"]


@pytest.mark.asyncio
async def test_run_prompt_once_interrupt_rolls_back_only_persisted_user_input(
    monkeypatch,
    tmp_path,
):
    streams: list[PersistingIdleCancellableStream] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            stream = PersistingIdleCancellableStream(
                session,
                [{"role": "user", "content": input}],
            )
            streams.append(stream)
            return stream

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "stop now",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        should_interrupt=lambda: True,
    )

    items = await DeepyJsonlSession.open(tmp_path, summary.session_id).get_items()
    assert summary.status == "interrupted"
    assert items == []
    assert streams[0].cancel_calls == ["immediate"]


@pytest.mark.asyncio
async def test_run_prompt_once_interrupt_preserves_tool_suffix_and_marks_turn(
    monkeypatch,
    tmp_path,
):
    streams: list[PersistingIdleCancellableStream] = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            stream = PersistingIdleCancellableStream(
                session,
                [
                    {"role": "user", "content": input},
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "read_file",
                        "arguments": "{}",
                    },
                ],
            )
            streams.append(stream)
            return stream

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "read then stop",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        should_interrupt=lambda: True,
    )

    items = await DeepyJsonlSession.open(tmp_path, summary.session_id).get_items()
    assert summary.status == "interrupted"
    assert items[:2] == [
        {"role": "user", "content": "read then stop"},
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "read_file",
            "arguments": "{}",
        },
    ]
    assert items[2] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "Tool execution interrupted by user with Esc.",
    }
    assert items[3]["role"] == "assistant"
    assert "Interrupted by user with Esc" in items[3]["content"]
    assert "Do not continue" in items[3]["content"]
    assert streams[0].cancel_calls == ["immediate"]


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
