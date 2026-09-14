from __future__ import annotations

import json
import pytest
import httpx
from agents import Agent, Runner, function_tool
from openai import AsyncOpenAI

from deepy.config import Settings
from deepy.config.providers import PROVIDER_CATALOG
from deepy.llm.provider import DeepyResponsesModel, build_provider_bundle
from deepy.llm.thinking import build_model_settings


@pytest.mark.parametrize("info", PROVIDER_CATALOG, ids=lambda p: p.id)
@pytest.mark.asyncio
async def test_responses_function_continuation(info):
    calls = []

    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.url.path.endswith("/responses")
        assert body["model"] == info.default_model
        assert body["store"] is False
        output = (
            [
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "echo",
                    "arguments": '{"value":"ok"}',
                    "status": "completed",
                }
            ]
            if len(calls) == 1
            else [
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "done", "annotations": []}],
                }
            ]
        )
        return httpx.Response(
            200,
            json={
                "id": f"resp_{len(calls)}",
                "object": "response",
                "created_at": 1,
                "model": info.default_model,
                "status": "completed",
                "output": output,
                "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
            },
        )

    async with AsyncOpenAI(
        api_key="test",
        base_url=info.default_base_url,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    ) as client:
        settings = Settings.from_mapping({"active_provider": info.id})
        model = DeepyResponsesModel(
            provider=info.id, model=info.default_model, openai_client=client
        )

        @function_tool
        def echo(value: str) -> str:
            return value

        result = await Runner.run(
            Agent(
                name="test",
                model=model,
                model_settings=build_model_settings(settings),
                tools=[echo],
            ),
            "call echo",
        )
        assert result.final_output == "done"
    assert len(calls) == 2
    assert any(
        item.get("type") == "function_call_output"
        and item["call_id"] == "call_1"
        and item["output"] == "ok"
        for item in calls[1]["input"]
    )


def test_missing_key_and_selected_identity():
    with pytest.raises(ValueError, match="API key missing"):
        build_provider_bundle(Settings())
    settings = Settings.from_mapping(
        {"active_provider": "kimi", "providers": {"kimi": {"api_key": "test"}}}
    )
    bundle = build_provider_bundle(settings)
    assert isinstance(bundle.model, DeepyResponsesModel)
    assert bundle.model.provider == "kimi"
    assert bundle.model.model == "kimi-k3"


@pytest.mark.parametrize("status", ["incomplete", "failed", "cancelled"])
@pytest.mark.asyncio
async def test_nonstream_partial_response_is_not_success(status):
    from agents.exceptions import ModelBehaviorError

    async with AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "id": "resp_1",
                        "object": "response",
                        "created_at": 1,
                        "model": "deepseek-flash",
                        "status": status,
                        "output": [],
                    },
                )
            )
        ),
    ) as client:
        model = DeepyResponsesModel(
            provider="deepseek", model="deepseek-flash", openai_client=client
        )
        with pytest.raises(ModelBehaviorError, match="did not complete"):
            await Runner.run(Agent(name="test", model=model), "hello")


@pytest.mark.parametrize("status", ["incomplete", "failed"])
@pytest.mark.asyncio
async def test_stream_partial_usage_precedes_recoverable_failure(monkeypatch, status):
    from types import SimpleNamespace
    from agents import OpenAIResponsesModel
    from agents.exceptions import ModelBehaviorError
    from deepy.llm.events import normalize_stream_event

    async def events(self, *args, **kwargs):
        yield SimpleNamespace(
            type=f"response.{status}",
            response=SimpleNamespace(output=[], usage={"input_tokens": 2, "output_tokens": 1}),
        )

    monkeypatch.setattr(OpenAIResponsesModel, "stream_response", events)
    async with AsyncOpenAI(api_key="test") as client:
        model = DeepyResponsesModel(
            provider="deepseek", model="deepseek-flash", openai_client=client
        )
        observed = []
        with pytest.raises(ModelBehaviorError):
            async for event in model.stream_response():
                observed.append(
                    normalize_stream_event(SimpleNamespace(type="raw_response_event", data=event))
                )
    assert len(observed) == 1 and observed[0].kind == "usage"


@pytest.mark.asyncio
async def test_tool_continuation_budget_rejects_before_second_http_and_preserves_work(tmp_path):
    from deepy.config.model_limits import resolve_model_limits
    from deepy.llm.request_budget import RequestBudgetError
    from deepy.llm.runner_history import preserve_completed_items
    from deepy.sessions import DeepySession

    http_calls, tool_calls = [], []
    def handle(request):
        http_calls.append(json.loads(request.content))
        item = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "large_result",
                "arguments": "{}", "status": "completed"}
        response = {"id": "resp_1", "object": "response", "created_at": 1,
                    "model": "deepseek-flash", "status": "completed", "output": [item],
                    "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}}
        events = [
            {"type": "response.created", "sequence_number": 0, "response": {**response, "status": "in_progress", "output": []}},
            {"type": "response.output_item.added", "sequence_number": 1, "output_index": 0, "item": item},
            {"type": "response.output_item.done", "sequence_number": 2, "output_index": 0, "item": item},
            {"type": "response.completed", "sequence_number": 3, "response": response},
        ]
        content = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)

    @function_tool
    def large_result() -> str:
        tool_calls.append(1)
        return "large " * 20000

    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    async with AsyncOpenAI(api_key="test", base_url="https://example.test/v1",
                          http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))) as client:
        model = DeepyResponsesModel(provider="deepseek", model="deepseek-flash", openai_client=client,
                                    limits=resolve_model_limits("deepseek", "deepseek-flash", global_cap=60000))
        result = Runner.run_streamed(Agent(name="test", model=model, tools=[large_result],
                                          model_settings=build_model_settings(Settings())),
                                     "call large_result", session=session)
        with pytest.raises(RequestBudgetError):
            async for _ in result.stream_events():
                pass
        await preserve_completed_items(session, result, 0)
    assert len(http_calls) == 1
    assert tool_calls == [1]
    assert http_calls[0]["max_output_tokens"] == 32768
    outputs = [item for item in await session.get_items() if item.get("type") == "function_call_output"]
    assert len(outputs) == 1
    assert outputs[0]["output"].startswith("large ")
    # Reapplying the recovery helper is idempotent.
    await preserve_completed_items(session, result, 0)
    assert len([item for item in await session.get_items() if item.get("type") == "function_call_output"]) == 1
