from __future__ import annotations

from deepy.config.settings import ModelConfig, Settings
from deepy.llm.provider import build_provider_bundle, should_replay_deepseek_reasoning_content


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

    assert bundle.model.should_replay_reasoning_content is should_replay_deepseek_reasoning_content
