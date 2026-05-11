from __future__ import annotations

import json
from collections.abc import Callable
from math import ceil
from typing import Any

from deepy.config import Settings


def estimate_tokens_for_text(text: str) -> int:
    if not text:
        return 0
    return max(1, ceil(len(text) / 4))


def estimate_tokens_for_item(item: Any) -> int:
    if isinstance(item, str):
        return estimate_tokens_for_text(item)
    if isinstance(item, dict):
        total = 0
        for key in ("role", "type", "name", "content", "output"):
            if key in item:
                total += estimate_tokens_for_item(item[key])
        if total:
            return total
        return estimate_tokens_for_text(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    if isinstance(item, list):
        return sum(estimate_tokens_for_item(part) for part in item)
    return estimate_tokens_for_text(str(item))


def estimate_tokens_for_items(items: list[dict[str, Any]]) -> int:
    return sum(estimate_tokens_for_item(item) for item in items)


def compact_items_for_context(
    history: list[dict[str, Any]],
    new_input: list[dict[str, Any]],
    *,
    threshold_tokens: int,
) -> list[dict[str, Any]]:
    combined = history + new_input
    if estimate_tokens_for_items(combined) <= threshold_tokens:
        return combined

    recent: list[dict[str, Any]] = []
    recent_tokens = estimate_tokens_for_items(new_input)
    budget = max(threshold_tokens - _compact_notice_token_budget(), 1)

    for item in reversed(history):
        item_tokens = estimate_tokens_for_item(item)
        if recent and recent_tokens + item_tokens > budget:
            break
        if recent_tokens + item_tokens > budget:
            continue
        recent.insert(0, item)
        recent_tokens += item_tokens

    omitted = len(history) - len(recent)
    if omitted <= 0:
        return recent + new_input

    notice = {
        "role": "system",
        "content": (
            "Earlier conversation history was compacted by Deepy to fit the configured context "
            f"window. Omitted history items: {omitted}. Continue using the remaining recent "
            "history and the current user request."
        ),
    }
    return [notice] + recent + new_input


def build_session_input_callback(settings: Settings) -> Callable[
    [list[dict[str, Any]], list[dict[str, Any]]],
    list[dict[str, Any]],
]:
    threshold = settings.context.resolved_compact_threshold

    def callback(history: list[dict[str, Any]], new_input: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return compact_items_for_context(
            history,
            new_input,
            threshold_tokens=threshold,
        )

    return callback


def _compact_notice_token_budget() -> int:
    return 80
