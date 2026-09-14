"""Documented limits and conservative, user-capped request budgets.

1M/128K notation is not evidence of binary units. Unknown input/output
relationships use a shared-window policy. Proxy references are not probes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

DEFAULT_OUTPUT_TOKENS = 32_768
SUMMARY_OUTPUT_TOKENS = 8_192
ESTIMATION_ALLOWANCE = 4_096


@dataclass(frozen=True)
class ModelLimits:
    provider: str
    model: str
    nominal_window: str
    exact_window_tokens: int | None
    runtime_window_tokens: int
    max_output_tokens: int
    source: str
    url: str
    api: str = "responses"
    checked_date: str = "2026-09-15"
    relationship: str = "conservative-shared"


_BASE = (
    ModelLimits("deepseek", "deepseek-flash", "1M", None, 1_000_000, 384_000,
                "conservative", "https://api-docs.deepseek.com/quick_start/pricing/"),
    *(ModelLimits("mimo", model, "1M", None, 1_000_000, 128_000,
                  "conservative", "https://mimo.mi.com/docs/zh-CN/quick-start/summary/model")
      for model in ("mimo-v2.5", "mimo-v2.5-pro")),
    ModelLimits("kimi", "kimi-k3", "1M", None, 1_000_000, 1_048_576,
                "conservative", "https://platform.kimi.com/docs/api/responses"),
    *(ModelLimits("cli_proxy", model, "1,050,000", 1_050_000, 1_050_000, 128_000,
                  "proxy-unverified", f"https://developers.openai.com/api/docs/models/{model}")
      for model in ("gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5")),
)
MODEL_LIMITS = {(item.provider, item.model): item for item in _BASE}


@dataclass(frozen=True)
class ResolvedModelLimits:
    catalog: ModelLimits
    window_tokens: int
    output_tokens: int
    reserve_tokens: int
    reserve_floor: int
    global_cap: int | None
    model_cap: int | None
    output_override: int | None

    @property
    def source(self) -> str:
        return ("user-cap/" if self.global_cap or self.model_cap else "") + self.catalog.source

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "source": self.source, "estimator": "cl100k_base-estimate"}


def positive_limit(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer.")
    return value


def resolve_model_limits(
    provider: str, model: str, *, global_cap: int | None = None,
    overrides: Mapping[str, Any] | None = None, reserve_floor: int = 50_000,
) -> ResolvedModelLimits:
    catalog = MODEL_LIMITS.get((provider, model))
    if catalog is None:
        raise ValueError(f"Unknown model limits: {provider}/{model}.")
    raw = overrides or {}
    if set(raw) - {"context_window_tokens", "max_output_tokens"}:
        raise ValueError(f"Unknown model limit field for {provider}/{model}.")
    cap = raw.get("context_window_tokens")
    output = raw.get("max_output_tokens")
    if cap is not None:
        positive_limit(cap, "context_window_tokens")
        if cap > catalog.runtime_window_tokens:
            raise ValueError("context_window_tokens cannot exceed the catalog runtime limit.")
    if global_cap is not None:
        positive_limit(global_cap, "context.window_tokens")
    requested = positive_limit(output, "max_output_tokens") if output is not None else DEFAULT_OUTPUT_TOKENS
    if requested > catalog.max_output_tokens:
        raise ValueError("max_output_tokens exceeds the model output limit.")
    window = min(catalog.runtime_window_tokens, global_cap or catalog.runtime_window_tokens,
                 cap or catalog.runtime_window_tokens)
    reserve = max(reserve_floor, requested + ESTIMATION_ALLOWANCE)
    if reserve >= window:
        raise ValueError("Context cap cannot fit output and safety reserve; lower max_output_tokens and reserved_context_tokens.")
    return ResolvedModelLimits(catalog, window, requested, reserve, reserve_floor, global_cap, cap, output)


def validate_profile_limits(provider: str, profile: Mapping[str, Any], *,
                            global_cap: int | None, reserve_floor: int) -> None:
    limits = profile.get("model_limits", {})
    if not isinstance(limits, Mapping):
        raise ValueError("model_limits must be a model-keyed table.")
    for model, raw in limits.items():
        if not isinstance(raw, Mapping):
            raise ValueError("Each model limit must be a table.")
        resolve_model_limits(provider, model, global_cap=global_cap,
                             overrides=raw, reserve_floor=reserve_floor)
