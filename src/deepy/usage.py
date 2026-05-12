from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    reasoning_tokens: int = 0
    requests: int = 0
    request_usage_entries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def known(self) -> bool:
        return any(
            (
                self.prompt_tokens,
                self.completion_tokens,
                self.total_tokens,
                self.prompt_cache_hit_tokens,
                self.prompt_cache_miss_tokens,
                self.reasoning_tokens,
                self.requests,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value not in (0, [], None)}


def normalize_usage(value: Any) -> TokenUsage:
    payload = _to_mapping(value)
    if payload is None:
        return TokenUsage()

    prompt_tokens = _int_field(payload.get("prompt_tokens"))
    completion_tokens = _int_field(payload.get("completion_tokens"))
    total_tokens = _int_field(payload.get("total_tokens"))

    sdk_input_tokens = _int_field(payload.get("input_tokens"))
    sdk_output_tokens = _int_field(payload.get("output_tokens"))
    if prompt_tokens == 0:
        prompt_tokens = sdk_input_tokens
    if completion_tokens == 0:
        completion_tokens = sdk_output_tokens
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    prompt_details = _to_mapping(payload.get("prompt_tokens_details")) or {}
    completion_details = _to_mapping(payload.get("completion_tokens_details")) or {}
    input_details = _to_mapping(payload.get("input_tokens_details")) or {}
    output_details = _to_mapping(payload.get("output_tokens_details")) or {}

    prompt_cache_hit_tokens = _first_int(
        payload.get("prompt_cache_hit_tokens"),
        prompt_details.get("cached_tokens"),
        input_details.get("cached_tokens"),
    )
    prompt_cache_miss_tokens = _int_field(payload.get("prompt_cache_miss_tokens"))
    if prompt_cache_miss_tokens == 0 and prompt_tokens and prompt_cache_hit_tokens:
        prompt_cache_miss_tokens = max(prompt_tokens - prompt_cache_hit_tokens, 0)
    reasoning_tokens = _first_int(
        completion_details.get("reasoning_tokens"),
        output_details.get("reasoning_tokens"),
    )

    request_entries = _request_usage_entries(payload.get("request_usage_entries"))
    if not request_entries and payload:
        entry = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if prompt_cache_hit_tokens:
            entry["prompt_cache_hit_tokens"] = prompt_cache_hit_tokens
        if prompt_cache_miss_tokens:
            entry["prompt_cache_miss_tokens"] = prompt_cache_miss_tokens
        if reasoning_tokens:
            entry["reasoning_tokens"] = reasoning_tokens
        if any(entry.values()):
            request_entries = [entry]
    requests = _int_field(payload.get("requests"))
    if requests == 0 and request_entries:
        requests = len(request_entries)

    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_cache_hit_tokens=prompt_cache_hit_tokens,
        prompt_cache_miss_tokens=prompt_cache_miss_tokens,
        reasoning_tokens=reasoning_tokens,
        requests=requests,
        request_usage_entries=request_entries,
    )


def merge_usage(*items: TokenUsage | Mapping[str, Any] | None) -> TokenUsage:
    total = TokenUsage()
    for item in items:
        usage = item if isinstance(item, TokenUsage) else normalize_usage(item)
        if not usage.known:
            continue
        total = TokenUsage(
            prompt_tokens=total.prompt_tokens + usage.prompt_tokens,
            completion_tokens=total.completion_tokens + usage.completion_tokens,
            total_tokens=total.total_tokens + usage.total_tokens,
            prompt_cache_hit_tokens=total.prompt_cache_hit_tokens + usage.prompt_cache_hit_tokens,
            prompt_cache_miss_tokens=total.prompt_cache_miss_tokens + usage.prompt_cache_miss_tokens,
            reasoning_tokens=total.reasoning_tokens + usage.reasoning_tokens,
            requests=total.requests + usage.requests,
            request_usage_entries=[
                *total.request_usage_entries,
                *usage.request_usage_entries,
            ],
        )
    return total


def usage_from_run_result(result: Any) -> TokenUsage:
    context = getattr(result, "context_wrapper", None)
    usage = getattr(context, "usage", None)
    return normalize_usage(usage)


def format_usage_line(usage: TokenUsage | Mapping[str, Any] | None) -> str:
    normalized = usage if isinstance(usage, TokenUsage) else normalize_usage(usage)
    if not normalized.known:
        return "usage=unknown"
    parts = [f"context input {normalized.prompt_tokens:,}"]
    cache_tokens = normalized.prompt_cache_hit_tokens + normalized.prompt_cache_miss_tokens
    if cache_tokens:
        cache_hit_rate = normalized.prompt_cache_hit_tokens / cache_tokens * 100
        parts.append(f"fresh input {normalized.prompt_cache_miss_tokens:,}")
        parts.append(
            f"cached input {normalized.prompt_cache_hit_tokens:,} "
            f"({cache_hit_rate:.1f}% hit)"
        )
    parts.append(f"output {normalized.completion_tokens:,}")
    if normalized.reasoning_tokens:
        parts.append(f"reasoning {normalized.reasoning_tokens:,}")
    parts.append(f"total {normalized.total_tokens:,}")
    return " · ".join(parts)


def _to_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, Mapping) else None
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return None


def _int_field(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float) and value.is_integer():
        return max(int(value), 0)
    return 0


def _first_int(*values: Any) -> int:
    for value in values:
        number = _int_field(value)
        if number:
            return number
    return 0


def _request_usage_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in value:
        normalized = normalize_usage(item)
        if normalized.known:
            payload = normalized.to_dict()
            payload.pop("request_usage_entries", None)
            entries.append(payload)
    return entries
