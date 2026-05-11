from __future__ import annotations

from typing import Any

from deepy.config import Settings


def build_thinking_extra_body(
    thinking_enabled: bool,
    reasoning_effort: str = "max",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
    }
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
        ),
    )
