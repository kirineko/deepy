from __future__ import annotations

from dataclasses import dataclass

from deepy.config import Settings


@dataclass(frozen=True)
class ProviderBundle:
    client: object
    model: object
    model_settings: object


def should_replay_deepseek_reasoning_content(context: object) -> bool:
    model = str(getattr(context, "model", "")).lower()
    if "deepseek" not in model:
        return False

    reasoning = getattr(context, "reasoning", None)
    origin_model = getattr(reasoning, "origin_model", None)
    provider_data = getattr(reasoning, "provider_data", {}) or {}
    return (
        isinstance(origin_model, str)
        and "deepseek" in origin_model.lower()
    ) or provider_data == {}


def build_provider_bundle(settings: Settings) -> ProviderBundle:
    from agents import OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI

    from .thinking import build_model_settings

    if not settings.model.api_key:
        raise ValueError(f"DeepSeek API key is missing in {settings.path or 'Deepy config'}.")

    set_tracing_disabled(disabled=True)
    client = AsyncOpenAI(base_url=settings.model.base_url, api_key=settings.model.api_key)
    model = OpenAIChatCompletionsModel(
        model=settings.model.name,
        openai_client=client,
        should_replay_reasoning_content=should_replay_deepseek_reasoning_content,
    )
    return ProviderBundle(client=client, model=model, model_settings=build_model_settings(settings))
