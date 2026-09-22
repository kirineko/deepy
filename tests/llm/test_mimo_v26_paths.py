"""Exercise shared Responses routing for both new MiMo models offline."""

from types import SimpleNamespace

import pytest
from agents import OpenAIResponsesModel

from deepy.cli import _doctor_live
from deepy.config import Settings
from deepy.llm.compaction import run_compaction_model
from deepy.llm.events import normalize_stream_event
from deepy.llm.provider import DeepyResponsesModel, build_provider_bundle


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["mimo-v2.6-flash", "mimo-v2.6-pro"])
@pytest.mark.parametrize("mode,effort", [("disabled", "none"), ("enabled", "high")])
async def test_main_doctor_compaction_and_stream_identity(monkeypatch, model, mode, effort):
    settings = Settings.from_mapping({"active_provider": "mimo", "providers": {
        "mimo": {"model": model, "reasoning": mode, "api_key": "test"}}})
    bundle = build_provider_bundle(settings)
    assert isinstance(bundle.model, DeepyResponsesModel)
    assert bundle.model.model == model
    calls = []

    async def run(agent, *args, **kwargs):
        assert isinstance(agent.model, DeepyResponsesModel)
        assert agent.model.model == model and agent.model.provider == "mimo"
        assert agent.model_settings.reasoning.effort == effort
        assert agent.model_settings.store is False
        calls.append(agent.model_settings.max_tokens)
        return SimpleNamespace(final_output="OK")

    monkeypatch.setattr("agents.Runner.run", run)
    report = await _doctor_live(settings)
    assert report["model"] == model and report["response_summary"] == "OK"
    summary, _ = await run_compaction_model(
        [{"role": "user", "content": "old"}], settings, provider=bundle
    )
    assert summary == "OK" and calls == [32768, 8192]

    reasoning = SimpleNamespace(type="reasoning")

    async def stream(self, *args, **kwargs):
        yield SimpleNamespace(type="response.reasoning_text.delta", delta="think")
        yield SimpleNamespace(type="response.output_text.delta", delta="OK")
        yield SimpleNamespace(type="response.completed", response=SimpleNamespace(
            output=[reasoning], usage={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}
        ))

    monkeypatch.setattr(OpenAIResponsesModel, "stream_response", stream)
    events = [normalize_stream_event(SimpleNamespace(type="raw_response_event", data=event))
              async for event in bundle.model.stream_response()]
    assert [event.kind for event in events] == ["reasoning_delta", "text_delta", "usage"]
    assert reasoning.deepy_origin == bundle.model.origin
    await bundle.client.close()
