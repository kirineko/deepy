from __future__ import annotations

from math import ceil
from typing import Any

from deepy.config import Settings
from deepy.llm.multimodal import item_contains_image_content, strip_image_content_from_items
from deepy.llm.multimodal import supports_image_input
from deepy.types.sdk import SessionInputCallback
from deepy.utils import json as json_utils

tiktoken: Any | None
try:
    import tiktoken as _tiktoken
except Exception:  # pragma: no cover - optional dependency fallback.
    tiktoken = None
else:
    tiktoken = _tiktoken

_ENCODING = None


def estimate_tokens_for_text(text: str) -> int:
    if not text:
        return 0
    encoding = _token_encoding()
    if encoding is not None:
        return max(1, len(encoding.encode(text)))
    return max(1, ceil(len(text) / 4))


def estimate_tokens_for_item(item: Any) -> int:
    if item_contains_image_content(item):
        return _estimate_multimodal_item_tokens(item)
    if isinstance(item, str):
        return estimate_tokens_for_text(item)
    if isinstance(item, dict):
        return estimate_tokens_for_text(json_utils.dumps(item))
    if isinstance(item, list):
        return sum(estimate_tokens_for_item(part) for part in item)
    return estimate_tokens_for_text(str(item))


def _estimate_multimodal_item_tokens(item: Any) -> int:
    if not isinstance(item, dict):
        return estimate_tokens_for_text(str(item))
    content = item.get("content")
    if not isinstance(content, list):
        return estimate_tokens_for_text(json_utils.dumps(item))
    tokens = 0
    for part in content:
        if not isinstance(part, dict):
            tokens += estimate_tokens_for_item(part)
            continue
        if part.get("type") in {"input_image", "image", "image_url"} or "image_url" in part:
            tokens += 1024
            continue
        tokens += estimate_tokens_for_item(part)
    return max(tokens, 1)


def estimate_tokens_for_items(items: list[dict[str, Any]]) -> int:
    return sum(estimate_tokens_for_item(item) for item in items)


def build_session_input_callback(settings: Settings) -> SessionInputCallback:
    def callback(history: list[Any], new_input: list[Any]) -> list[Any]:
        items = [*history, *new_input]
        if not supports_image_input(settings):
            return strip_image_content_from_items(items)
        return items

    return callback


def should_auto_compact(
    token_count: int,
    max_context_size: int,
    *,
    trigger_ratio: float,
    reserved_context_size: int,
) -> bool:
    if token_count <= 0 or max_context_size <= 0:
        return False
    return (
        token_count >= max_context_size * trigger_ratio
        or token_count + reserved_context_size >= max_context_size
    )


def _token_encoding() -> Any | None:
    global _ENCODING
    if _ENCODING is not None:
        return _ENCODING
    if tiktoken is None:
        return None
    try:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None
    return _ENCODING
