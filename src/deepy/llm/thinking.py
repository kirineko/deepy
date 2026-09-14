from __future__ import annotations

from agents import ModelSettings
from openai.types.shared import Reasoning

from deepy.config import Settings


def build_model_settings(settings: Settings) -> ModelSettings:
    mode = settings.model.reasoning_mode
    effort = (
        ("high" if mode == "enabled" else "none") if settings.model.provider == "mimo" else mode
    )
    # Catalog validation includes the DeepSeek/Kimi extension "max", absent from OpenAI literals.
    reasoning = Reasoning.model_construct(effort=effort)
    if settings.model.provider == "cli_proxy" and effort != "none":
        reasoning.summary = "auto"
    return ModelSettings(include_usage=True, store=False, reasoning=reasoning,
                         max_tokens=settings.model_limits.output_tokens)
