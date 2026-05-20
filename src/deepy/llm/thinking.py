from __future__ import annotations

from typing import Any

from deepy.config import Settings


def build_thinking_extra_body(
    thinking_enabled: bool,
    reasoning_effort: str = "max",
    *,
    provider: str = "deepseek",
) -> dict[str, Any]:
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


def build_model_settings(settings: Settings):
    from agents import ModelSettings

    return ModelSettings(
        include_usage=True,
        store=False,
        extra_body=build_thinking_extra_body(
            settings.model.thinking_enabled,
            settings.model.reasoning_effort,
            provider=settings.model.provider,
        ),
    )
