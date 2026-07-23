from __future__ import annotations

from typing import Any, Literal, cast

from deepy.config import Settings
from deepy.config.providers import LOCALHOST_REASONING_EFFORTS, PROVIDER_API_RESPONSES

LocalhostReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]


def build_thinking_extra_body(
    thinking_enabled: bool,
    reasoning_effort: str = "max",
    *,
    provider: str = "deepseek",
) -> dict[str, Any]:
    if provider == "localhost":
        effort = reasoning_effort if thinking_enabled else "none"
        if effort not in LOCALHOST_REASONING_EFFORTS:
            effort = "none"
        return {"reasoning_effort": effort}
    body: dict[str, Any] = {
        "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
    }
    if provider == "xiaomi":
        return body
    if provider == "openrouter":
        effort = reasoning_effort if thinking_enabled else "none"
        if effort in {"none", "disabled"}:
            return {"reasoning": {"enabled": False}}
        reasoning: dict[str, Any] = {"enabled": True}
        if effort in {"xhigh", "high", "medium", "low", "minimal"}:
            reasoning["effort"] = effort
        return {"reasoning": reasoning}
    if thinking_enabled:
        body["reasoning_effort"] = reasoning_effort if reasoning_effort in {"high", "max"} else "max"
    return body


def _localhost_reasoning_effort(settings: Settings) -> LocalhostReasoningEffort:
    from deepy.config.providers import provider_info_for

    provider_info = provider_info_for(settings.model.provider)
    effort = settings.model.reasoning_effort
    if effort not in LOCALHOST_REASONING_EFFORTS:
        effort = provider_info.default_thinking_mode
    if not settings.model.thinking_enabled:
        effort = "none"
    return cast(LocalhostReasoningEffort, effort)


def build_model_settings(settings: Settings):
    from agents import ModelSettings
    from openai.types.shared import Reasoning

    from deepy.config.providers import provider_info_for

    provider_info = provider_info_for(settings.model.provider)
    if provider_info.api == PROVIDER_API_RESPONSES:
        effort = _localhost_reasoning_effort(settings)
        return ModelSettings(
            include_usage=True,
            store=False,
            reasoning=Reasoning(
                effort=effort,
                summary=None if effort == "none" else "auto",
            ),
        )
    return ModelSettings(
        include_usage=True,
        store=False,
        extra_body=build_thinking_extra_body(
            settings.model.thinking_enabled,
            settings.model.reasoning_effort,
            provider=settings.model.provider,
        ),
    )
