"""One context display policy for both interfaces and diagnostics."""
from __future__ import annotations

from typing import Any
from deepy.config import Settings
from deepy.llm.history_projection import model_identity


def context_display(entry: Any, settings: Settings) -> tuple[int | None, str]:
    if entry is None:
        return None, "pending"
    state = getattr(entry, "history_state", None) or {}
    checkpoint = state.get("checkpoint", {})
    target = model_identity(settings.model.provider, settings.model.name, settings.model.base_url)
    if checkpoint.get("target") == target and checkpoint.get("prefix") == getattr(entry, "cache_prefix_fingerprint", None):
        value = getattr(entry, "latest_context_window_tokens", None)
        if value is not None:
            return value + getattr(entry, "pending_tokens", 0), "estimated" if getattr(entry, "pending_tokens", 0) else "reported"
    return getattr(entry, "active_tokens", 0), "estimated / pending validation"


def context_label(entry: Any, settings: Settings) -> str:
    value, state = context_display(entry, settings)
    limits = settings.model_limits
    used = "-" if value is None else compact_tokens(value)
    if value is not None and state != "reported":
        used = f"~{used}"
    source = {"conservative": "~", "proxy-unverified": "?"}.get(limits.catalog.source, "")
    total = f"{compact_tokens(limits.window_tokens)}{source}"
    percentage = f" ({value / limits.window_tokens:.1%})" if value is not None else ""
    hint = " !" if value is not None and (
        value >= limits.window_tokens * settings.context.compact_trigger_ratio
        or value + limits.reserve_tokens >= limits.window_tokens) else ""
    return f"ctx {used}/{total}{percentage}{hint}"


def compact_tokens(value: int) -> str:
    if value >= 999_950:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if value >= 1000:
        return f"{value / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(value)
