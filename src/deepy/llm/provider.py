from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents import Model, ModelSettings, OpenAIResponsesModel

from deepy.config import Settings
from deepy.config.model_limits import ResolvedModelLimits, resolve_model_limits
from .history_projection import model_identity, project_history, history_groups
from .request_budget import check_request

from .cache_context import capture_sdk_request_shape
from .response_images import normalize_response_images, validate_encoded_request
from .multimodal import (
    items_contain_image_content,
    model_supports_image_input,
    UnsupportedImageInputError,
)


@dataclass(frozen=True)
class ProviderBundle:
    client: object
    model: Model
    model_settings: ModelSettings


class DeepyResponsesModel(OpenAIResponsesModel):
    """Keep provider identity explicit even when users override the endpoint."""

    def __init__(self, *, provider: str, limits: ResolvedModelLimits | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.provider = provider
        self.limits = limits or resolve_model_limits(provider, self.model)
        self.origin = model_identity(provider, self.model, str(self._client.base_url))

    def _tag_reasoning(self, items: list[Any]) -> None:
        for item in items:
            if item is not None:
                setattr(item, "deepy_origin", self.origin)
            if getattr(item, "type", None) == "reasoning":
                setattr(item, "deepy_provider", self.provider)

    async def _fetch_response(self, *args: Any, **kwargs: Any) -> Any:
        from agents.exceptions import ModelBehaviorError

        response = await super()._fetch_response(*args, **kwargs)
        if getattr(response, "status", None) in {"incomplete", "failed", "cancelled"}:
            raise ModelBehaviorError(
                "Provider response did not complete. Please retry or reduce context."
            )
        return response

    async def get_response(self, *args: Any, **kwargs: Any) -> Any:
        response = await super().get_response(*args, **kwargs)
        self._tag_reasoning(response.output)
        return response

    async def stream_response(self, *args: Any, **kwargs: Any) -> Any:
        from agents.exceptions import ModelBehaviorError

        async for event in super().stream_response(*args, **kwargs):
            if event.type == "response.output_item.done":
                self._tag_reasoning([getattr(event, "item", None)])
            response = getattr(event, "response", None)
            if response is not None:
                self._tag_reasoning(response.output or [])
            yield event
            if event.type in {"response.incomplete", "response.failed"}:
                raise ModelBehaviorError(
                    "Provider response did not complete. Please retry or reduce context."
                )

    def _build_response_create_kwargs(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        names = (
            "system_instructions",
            "input",
            "model_settings",
            "tools",
            "output_schema",
            "handoffs",
            "previous_response_id",
            "conversation_id",
            "stream",
            "prompt",
        )
        kwargs = {**dict(zip(names, args)), **kwargs}
        items = normalize_response_images(kwargs.get("input"))
        if isinstance(items, list) and items_contain_image_content(items):
            if not model_supports_image_input(self.provider, self.model):
                raise UnsupportedImageInputError(
                    "当前模型不支持会话中的图片，请切换图片模型或开始纯文本会话。原图片已保留。"
                )
        if isinstance(items, list):
            items = project_history(items, self.origin)
            history_groups(items)
        kwargs["input"] = items
        capture_sdk_request_shape(
            system_instructions=kwargs.get("system_instructions"),
            input=items,
            model=self.model,
            model_settings=kwargs.get("model_settings"),
            tools=kwargs.get("tools"),
            mcp_servers=None,
        )
        payload = super()._build_response_create_kwargs(**kwargs)
        if self.provider == "kimi" and payload.get("tool_choice") != "none":
            payload["tool_choice"] = "auto"
        if not isinstance(payload.get("max_output_tokens"), int):
            payload["max_output_tokens"] = self.limits.output_tokens
        check_request(payload, self.limits)
        return payload


def build_provider_bundle(settings: Settings) -> ProviderBundle:
    from agents import set_tracing_disabled
    from openai import AsyncOpenAI
    from .thinking import build_model_settings

    if not settings.model.api_key:
        raise ValueError(f"API key missing for {settings.model.provider}; run deepy config setup.")
    set_tracing_disabled(disabled=True)
    import httpx

    client = AsyncOpenAI(
        base_url=settings.model.base_url,
        api_key=settings.model.api_key,
        http_client=httpx.AsyncClient(event_hooks={"request": [validate_encoded_request]}),
    )
    model = DeepyResponsesModel(
        provider=settings.model.provider, model=settings.model.name, openai_client=client,
        limits=settings.model_limits
    )
    return ProviderBundle(client=client, model=model, model_settings=build_model_settings(settings))
