from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

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
        response = await super()._fetch_response(
            system_instructions,
            sanitize_model_input_for_chat_completions(input),
            *args,
            **kwargs,
        )
        preserve_openrouter_reasoning_content_alias(
            response,
            str(getattr(self._get_client(), "base_url", "") or ""),
        )
        return response


def preserve_openrouter_reasoning_content_alias(response: Any, base_url: str) -> None:
    if not _is_openrouter_base_url(base_url):
        return

    choices = getattr(response, "choices", None)
    if not isinstance(choices, list):
        return

    for choice in choices:
        message = getattr(choice, "message", None)
        if message is None or not getattr(message, "tool_calls", None):
            continue
        reasoning = getattr(message, "reasoning", None)
        if not isinstance(reasoning, str) or not reasoning.strip():
            continue
        existing = getattr(message, "reasoning_content", None)
        if isinstance(existing, str) and existing:
            continue
        setattr(message, "reasoning_content", reasoning)


def should_replay_chat_completion_reasoning_content(context: object) -> bool:
    model = str(getattr(context, "model", "")).lower()
    base_url = str(getattr(context, "base_url", "") or "").rstrip("/").lower()
    if "deepseek" in model:
        return _reasoning_origin_matches(context, "deepseek")
    if _is_direct_xiaomi_mimo(model, base_url):
        return _reasoning_origin_matches(context, "mimo")
    if _is_openrouter_base_url(base_url):
        return _reasoning_origin_matches_model(context, model)
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


def _reasoning_origin_matches_model(context: object, model: str) -> bool:
    reasoning = getattr(context, "reasoning", None)
    origin_model = getattr(reasoning, "origin_model", None)
    provider_data = getattr(reasoning, "provider_data", {}) or {}
    return (
        isinstance(origin_model, str)
        and origin_model.strip().lower() == model
    ) or provider_data == {}


def _is_direct_xiaomi_mimo(model: str, base_url: str) -> bool:
    if "xiaomimimo.com" not in base_url:
        return False
    return model in {"mimo-v2.5", "mimo-v2.5-pro"}


def _is_openrouter_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = (parsed.hostname or base_url).rstrip("/").lower()
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")


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
