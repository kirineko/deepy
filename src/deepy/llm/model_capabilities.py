from __future__ import annotations

DEEPSEEK_V4_MODELS = frozenset({"deepseek-v4-pro", "deepseek-v4-flash"})


def defaults_to_thinking_mode(model: str) -> bool:
    return model in DEEPSEEK_V4_MODELS
