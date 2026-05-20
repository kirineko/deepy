from __future__ import annotations

import json

import pytest

from deepy.config.settings import ModelConfig, Settings
from deepy.llm.provider import (
    DeepyOpenAIChatCompletionsModel,
    build_provider_bundle,
    should_replay_deepseek_reasoning_content,
)
from deepy.llm.thinking import build_model_settings


class Reasoning:
    def __init__(self, origin_model=None, provider_data=None):
        self.origin_model = origin_model
        self.provider_data = provider_data or {}


class ReplayContext:
    def __init__(self, model, reasoning):
        self.model = model
        self.reasoning = reasoning


def test_deepseek_reasoning_replay_only_for_deepseek_sources():
    assert should_replay_deepseek_reasoning_content(
        ReplayContext("deepseek-v4-pro", Reasoning(origin_model="deepseek-v4-pro"))
    )
    assert should_replay_deepseek_reasoning_content(
        ReplayContext("deepseek-v4-pro", Reasoning(provider_data={}))
    )
    assert not should_replay_deepseek_reasoning_content(
        ReplayContext("deepseek-v4-pro", Reasoning(origin_model="claude-4", provider_data={"x": 1}))
    )
    assert not should_replay_deepseek_reasoning_content(
        ReplayContext("gpt-5.5", Reasoning(origin_model="deepseek-v4-pro"))
    )


def test_provider_bundle_passes_explicit_reasoning_replay_hook():
    settings = Settings(model=ModelConfig(api_key="sk-test"))

    bundle = build_provider_bundle(settings)

    assert isinstance(bundle.model, DeepyOpenAIChatCompletionsModel)
    assert bundle.model.should_replay_reasoning_content is should_replay_deepseek_reasoning_content


def test_provider_bundle_uses_selected_model_name():
    settings = Settings(model=ModelConfig(api_key="sk-test", name="deepseek-v4-flash"))

    bundle = build_provider_bundle(settings)

    assert bundle.model.model == "deepseek-v4-flash"


def test_provider_bundle_uses_selected_provider_base_url_and_model():
    settings = Settings(
        model=ModelConfig(
            provider="openrouter",
            api_key="sk-test",
            name="xiaomi/mimo-v2.5-pro",
            base_url="https://openrouter.ai/api/v1",
        )
    )

    bundle = build_provider_bundle(settings)

    assert bundle.model.model == "xiaomi/mimo-v2.5-pro"
    assert str(bundle.client.base_url) == "https://openrouter.ai/api/v1/"


def test_model_settings_map_reasoning_modes_to_deepseek_body():
    disabled = build_model_settings(
        Settings(model=ModelConfig(api_key="sk-test", thinking=False))
    ).extra_body
    high = build_model_settings(
        Settings(model=ModelConfig(api_key="sk-test", thinking=True, reasoning_effort="high"))
    ).extra_body
    max_effort = build_model_settings(
        Settings(model=ModelConfig(api_key="sk-test", thinking=True, reasoning_effort="max"))
    ).extra_body

    assert disabled == {"thinking": {"type": "disabled"}}
    assert high == {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
    assert max_effort == {"thinking": {"type": "enabled"}, "reasoning_effort": "max"}


def test_model_settings_map_openrouter_reasoning_effort():
    enabled = build_model_settings(
        Settings(
            model=ModelConfig(
                provider="openrouter",
                name="google/gemini-3.5-flash",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test",
                thinking=True,
                reasoning_effort="enabled",
            )
        )
    )
    minimal = build_model_settings(
        Settings(
            model=ModelConfig(
                provider="openrouter",
                name="anthropic/claude-sonnet-4.5",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test",
                thinking=True,
                reasoning_effort="minimal",
            )
        )
    )
    disabled = build_model_settings(
        Settings(
            model=ModelConfig(
                provider="openrouter",
                name="xiaomi/mimo-v2.5",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test",
                thinking=False,
                reasoning_effort="none",
            )
        )
    )

    assert enabled.extra_body == {"reasoning": {"enabled": True}}
    assert minimal.extra_body == {"reasoning": {"enabled": True, "effort": "minimal"}}
    assert disabled.extra_body == {"reasoning": {"enabled": False}}
    assert minimal.include_usage is True
    assert minimal.store is False


def test_model_settings_map_xiaomi_mimo_switch_thinking_without_reasoning_effort():
    enabled = build_model_settings(
        Settings(
            model=ModelConfig(
                provider="xiaomi",
                name="mimo-v2.5-pro",
                base_url="https://api.xiaomimimo.com/v1",
                api_key="sk-test",
                thinking=True,
                reasoning_effort="enabled",
            )
        )
    ).extra_body
    disabled = build_model_settings(
        Settings(
            model=ModelConfig(
                provider="xiaomi",
                name="mimo-v2.5",
                base_url="https://api.xiaomimimo.com/v1",
                api_key="sk-test",
                thinking=False,
                reasoning_effort="none",
            )
        )
    ).extra_body

    assert enabled == {"thinking": {"type": "enabled"}}
    assert disabled == {"thinking": {"type": "disabled"}}


@pytest.mark.asyncio
async def test_deepy_model_sanitizes_replay_before_chat_completion_fetch(monkeypatch):
    from agents import OpenAIChatCompletionsModel

    captured_input = []

    async def fake_fetch(self, system_instructions, input, *args, **kwargs):
        captured_input.append(input)
        return object()

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", fake_fetch)
    model = build_provider_bundle(Settings(model=ModelConfig(api_key="sk-test"))).model
    call = {
        "arguments": '{"file_path":"README.md"}',
        "call_id": "call-read",
        "name": "read_file",
        "type": "function_call",
    }
    empty_message = {
        "id": "__fake_id__",
        "content": [{"annotations": [], "text": "", "type": "output_text"}],
        "role": "assistant",
        "status": "completed",
        "type": "message",
    }
    output = {
        "call_id": "call-read",
        "output": '{"ok":true}',
        "type": "function_call_output",
    }

    await model._fetch_response(
        None,
        [call, empty_message, output],
        object(),
        [],
        None,
        [],
        object(),
        object(),
        stream=False,
    )

    assert captured_input == [[call, output]]


@pytest.mark.asyncio
async def test_deepy_model_sends_deepseek_thinking_fields_in_chat_completion_body():
    import httpx
    from openai import AsyncOpenAI

    captured: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": str(request.url),
                "body": json.loads(request.content.decode()),
            }
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b"data: [DONE]\n\n",
        )

    class Tracing:
        def include_data(self) -> bool:
            return False

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenAI(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        http_client=http_client,
    )
    model = DeepyOpenAIChatCompletionsModel(
        model="deepseek-v4-pro",
        openai_client=client,
    )
    settings = Settings(
        model=ModelConfig(
            api_key="sk-test",
            thinking=True,
            reasoning_effort="max",
        )
    )

    await model._fetch_response(
        "You are a helpful assistant",
        "Hello",
        build_model_settings(settings),
        [],
        None,
        [],
        object(),
        Tracing(),
        stream=True,
    )
    await http_client.aclose()

    assert captured[0]["url"] == "https://api.deepseek.com/chat/completions"
    body = captured[0]["body"]
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-v4-pro"
    assert body["stream"] is True
    assert body["thinking"] == {"type": "enabled"}
    assert body["reasoning_effort"] == "max"
