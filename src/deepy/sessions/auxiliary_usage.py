"""Accumulate auxiliary usage without changing main conversation checkpoints."""

from __future__ import annotations

from typing import Any

from deepy.config.providers import PROVIDER_CATALOG
from deepy.usage import TokenUsage, merge_usage


def search_usage(
    previous: dict[str, Any], raw: dict[str, Any], usage: TokenUsage
) -> dict[str, Any]:
    result = merge_usage(previous, usage).to_dict()
    server = raw.get("server_tool_use")
    count = server.get("web_search_requests") if isinstance(server, dict) else None
    old_count = previous.get("search_requests", 0)
    result.update(provider="deepseek", model="deepseek-flash", purpose="web_search")
    result["search_requests"] = (old_count if isinstance(old_count, int) else 0) + (
        count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else 0
    )
    return result


def suggestion_usage(
    previous: dict[str, Any] | None, usage: TokenUsage, model: str, elapsed_ms: int | None
) -> dict[str, Any]:
    previous = previous or {}
    result = merge_usage(previous, usage).to_dict()
    provider = next(
        (p.id for p in PROVIDER_CATALOG if any(m.name == model for m in p.models)), "unknown"
    )
    breakdown = dict(previous.get("by_model") or {})
    identity = f"{provider}/{model}"
    breakdown[identity] = merge_usage(breakdown.get(identity), usage).to_dict()
    result.update(model=model, provider=provider, by_model=breakdown)
    if elapsed_ms is not None:
        result["elapsed_ms"] = max(previous.get("elapsed_ms", 0), 0) + max(elapsed_ms, 0)
    return result
