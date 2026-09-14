"""Budget real tool schemas as JSON, not as multimodal discriminators."""
from copy import deepcopy

import httpx
import pytest
from agents import Runner
from openai import AsyncOpenAI

from deepy.config import Settings
from deepy.config.model_limits import MODEL_LIMITS
from deepy.llm.agent import build_deepy_agent
from deepy.llm.provider import DeepyResponsesModel, ProviderBundle
from deepy.llm.request_budget import estimate_request_value
from deepy.llm.thinking import build_model_settings
from deepy.subagents import SubagentDiscoveryResult
from deepy.tools import ToolRuntime
from deepy.utils import json


@pytest.mark.parametrize("schema", [
    {"type": ["string", "null"], "description": "optional input"},
    {"type": {"type": "string", "description": "a property literally named type"}},
    {"type": "object", "properties": {"path": {"type": ["string", "null"]}}},
])
def test_schema_types_are_budgeted_without_mutation(schema):
    original = deepcopy(schema)
    assert estimate_request_value(schema) > 0
    assert estimate_request_value({**schema, "description": "explanation " * 100}) > estimate_request_value(schema)
    assert schema == original


@pytest.mark.parametrize("provider,model_name", MODEL_LIMITS)
@pytest.mark.asyncio
async def test_full_deepy_tools_stream_hi_through_request_budget(tmp_path, monkeypatch, provider, model_name):
    monkeypatch.setattr("deepy.llm.agent.discover_subagents", lambda root: SubagentDiscoveryResult(()))
    requests = []
    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        assert len(body["tools"]) > 5  # The real tool set, not the earlier single echo fixture.
        assert body["max_output_tokens"] == 32768
        item = {"type": "message", "id": "msg_hi", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "Hello!", "annotations": []}]}
        response = {"id": "resp_hi", "object": "response", "created_at": 1,
                    "model": model_name, "status": "completed", "output": [item],
                    "usage": {"input_tokens": 100, "output_tokens": 2, "total_tokens": 102}}
        events = [
            {"type": "response.created", "sequence_number": 0, "response": {**response, "status": "in_progress", "output": []}},
            {"type": "response.output_item.added", "sequence_number": 1, "output_index": 0, "item": item},
            {"type": "response.output_item.done", "sequence_number": 2, "output_index": 0, "item": item},
            {"type": "response.completed", "sequence_number": 3, "response": response},
        ]
        content = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)

    settings = Settings.from_mapping({"active_provider": provider, "providers": {provider: {"model": model_name}}})
    async with AsyncOpenAI(api_key="test", base_url=settings.model.base_url,
                          http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))) as client:
        model = DeepyResponsesModel(provider=provider, model=model_name, openai_client=client,
                                    limits=settings.model_limits)
        bundle = ProviderBundle(client=client, model=model, model_settings=build_model_settings(settings))
        agent = build_deepy_agent(settings, ToolRuntime(cwd=tmp_path, settings=settings),
                                 project_root=tmp_path, provider=bundle)
        result = Runner.run_streamed(agent, "hi", max_turns=1)
        async for _ in result.stream_events():
            pass
        assert result.final_output == "Hello!"
    assert len(requests) == 1
