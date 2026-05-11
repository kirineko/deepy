from __future__ import annotations

from dataclasses import dataclass

from deepy.config import Settings


@dataclass(frozen=True)
class ProviderBundle:
    client: object
    model: object
    model_settings: object


def build_provider_bundle(settings: Settings) -> ProviderBundle:
    from agents import OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI

    from .thinking import build_model_settings

    if not settings.model.api_key:
        raise ValueError(f"DeepSeek API key is missing in {settings.path or 'Deepy config'}.")

    set_tracing_disabled(disabled=True)
    client = AsyncOpenAI(base_url=settings.model.base_url, api_key=settings.model.api_key)
    model = OpenAIChatCompletionsModel(model=settings.model.name, openai_client=client)
    return ProviderBundle(client=client, model=model, model_settings=build_model_settings(settings))
