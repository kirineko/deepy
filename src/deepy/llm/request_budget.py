"""Budget the normalized outgoing request, including tool schemas and images."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.exceptions import ModelBehaviorError

from deepy.config.model_limits import ESTIMATION_ALLOWANCE, ResolvedModelLimits
from .context import estimate_tokens_for_text


class RequestBudgetError(ModelBehaviorError):
    def __init__(self, message: str, items: Any = None):
        super().__init__(message)
        self.items = items


def estimate_request_value(value: Any) -> int:
    if isinstance(value, dict):
        item_type = value.get("type")
        if isinstance(item_type, str) and item_type in {"input_image", "image", "image_url"}:
            return 1024
        return 4 + sum(estimate_tokens_for_text(str(k)) + estimate_request_value(v)
                       for k, v in value.items() if not str(k).startswith("deepy_"))
    if isinstance(value, (tuple, list)):
        return sum(estimate_request_value(part) for part in value)
    if value is None:
        return 0
    if isinstance(value, str) and value.startswith("data:image/"):
        return 1024
    return estimate_tokens_for_text(str(value))


@dataclass(frozen=True)
class RequestBudget:
    input_tokens: int
    output_tokens: int
    reserve_tokens: int
    window_tokens: int
    estimator: str = "cl100k_base-estimate"

    @property
    def fits(self) -> bool:
        return self.input_tokens + self.reserve_tokens < self.window_tokens

    def needs_compaction(self, ratio: float) -> bool:
        return not self.fits or self.input_tokens >= self.window_tokens * ratio


def request_budget(payload: dict[str, Any], limits: ResolvedModelLimits) -> RequestBudget:
    output = payload.get("max_output_tokens")
    if not isinstance(output, int):
        output = limits.output_tokens
    reserve = max(limits.reserve_floor, output + ESTIMATION_ALLOWANCE)
    tokens = sum(estimate_request_value(payload.get(key)) for key in
                 ("instructions", "input", "tools", "text", "prompt"))
    return RequestBudget(tokens, output, reserve, limits.window_tokens)


def check_request(payload: dict[str, Any], limits: ResolvedModelLimits) -> RequestBudget:
    budget = request_budget(payload, limits)
    if budget.output_tokens > limits.catalog.max_output_tokens or not budget.fits:
        raise RequestBudgetError(
            f"Context request estimate {budget.input_tokens:,} + reserve {budget.reserve_tokens:,} "
            f"cannot fit {budget.window_tokens:,}. Executed tools are retained; use /compact "
            "or switch to a larger configured window before retrying.", payload.get("input"))
    return budget
