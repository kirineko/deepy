"""Actionable guidance for model IDs removed from the supported catalog."""

_MIMO_REPLACEMENTS = {
    "mimo-v2.5": "mimo-v2.6-flash",
    "mimo-v2.5-pro": "mimo-v2.6-pro",
}


def retired_model_guidance(provider: str, model: str, *, limits: bool = False) -> str | None:
    replacement = _MIMO_REPLACEMENTS.get(model) if provider == "mimo" else None
    if replacement is None:
        return None
    if limits:
        return (
            f'Removed MiMo model {model}: rename providers.mimo.model_limits."{model}" '
            f'to providers.mimo.model_limits."{replacement}" or remove that override.'
        )
    return (
        f"Removed MiMo model {model}: edit providers.mimo.model to {replacement}. "
        "Update any matching providers.mimo.model_limits entry as well."
    )
