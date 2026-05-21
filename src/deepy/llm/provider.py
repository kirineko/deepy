from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents import Model, ModelSettings
from agents import OpenAIChatCompletionsModel

from deepy.config import Settings

from .replay import (
    sanitize_chat_completion_stream_event,
    sanitize_model_input_for_chat_completions,
    sanitize_model_response_output,
)


@dataclass(frozen=True)
class ProviderBundle:
    client: object
    model: Model
    model_settings: ModelSettings


class DeepyOpenAIChatCompletionsModel(OpenAIChatCompletionsModel):
    async def get_response(self, *args: Any, **kwargs: Any) -> Any:
        response = await super().get_response(*args, **kwargs)
        response.output = sanitize_model_response_output(response.output)
        return response

    async def stream_response(self, *args: Any, **kwargs: Any) -> Any:
        async for event in super().stream_response(*args, **kwargs):
            sanitized = sanitize_chat_completion_stream_event(event)
            if sanitized is not None:
                yield sanitized

    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return await super()._fetch_response(
            system_instructions,
            sanitize_model_input_for_chat_completions(input),
            *args,
            **kwargs,
        )


def should_replay_chat_completion_reasoning_content(context: object) -> bool:
    model = str(getattr(context, "model", "")).lower()
    base_url = str(getattr(context, "base_url", "") or "").rstrip("/").lower()
    if "deepseek" in model:
        return _reasoning_origin_matches(context, "deepseek")
    if _is_direct_xiaomi_mimo(model, base_url):
        return _reasoning_origin_matches(context, "mimo")
    return False


def should_replay_deepseek_reasoning_content(context: object) -> bool:
    return should_replay_chat_completion_reasoning_content(context)


def _reasoning_origin_matches(context: object, model_fragment: str) -> bool:
    reasoning = getattr(context, "reasoning", None)
    origin_model = getattr(reasoning, "origin_model", None)
    provider_data = getattr(reasoning, "provider_data", {}) or {}
    return (
        isinstance(origin_model, str)
        and model_fragment in origin_model.lower()
    ) or provider_data == {}


def _is_direct_xiaomi_mimo(model: str, base_url: str) -> bool:
    if "xiaomimimo.com" not in base_url:
        return False
    return model in {"mimo-v2.5", "mimo-v2.5-pro"}


def build_provider_bundle(settings: Settings) -> ProviderBundle:
    from agents import set_tracing_disabled
    from openai import AsyncOpenAI

    from .thinking import build_model_settings

    if not settings.model.api_key:
        raise ValueError(f"Model API key is missing in {settings.path or 'Deepy config'}.")

    set_tracing_disabled(disabled=True)
    client = AsyncOpenAI(base_url=settings.model.base_url, api_key=settings.model.api_key)
    model = DeepyOpenAIChatCompletionsModel(
        model=settings.model.name,
        openai_client=client,
        should_replay_reasoning_content=should_replay_chat_completion_reasoning_content,
    )
    return ProviderBundle(client=client, model=model, model_settings=build_model_settings(settings))
