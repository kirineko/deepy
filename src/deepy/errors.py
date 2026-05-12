from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorDisplay:
    category: str
    detail: str
    hint: str = ""


def classify_error(error: BaseException | str) -> ErrorDisplay:
    text = str(error).strip()
    normalized = text.casefold()
    status = _status_code(error)

    if status in {401, 403} or any(token in normalized for token in ("unauthorized", "forbidden")):
        return ErrorDisplay(
            category="api_auth",
            detail=text or "API authentication failed.",
            hint="Check the API key with `deepy config setup`.",
        )
    if status in {408, 429, 500, 502, 503, 504} or any(
        token in normalized
        for token in ("timeout", "timed out", "connection", "network", "dns", "temporarily")
    ):
        return ErrorDisplay(
            category="network",
            detail=text or "Network request failed.",
            hint="Retry later or check base_url and network connectivity.",
        )
    if any(token in normalized for token in ("tool", "functiontool", "max_turns", "run failed")):
        return ErrorDisplay(
            category="sdk_tool_failure",
            detail=text or "Agent or tool execution failed.",
            hint="Check the tool output above or rerun with debug logging enabled.",
        )
    if any(token in normalized for token in ("api_key", "api key", "config", "toml")):
        return ErrorDisplay(
            category="config",
            detail=text or "Deepy configuration is incomplete.",
            hint="Run `deepy config setup`.",
        )
    return ErrorDisplay(category="unknown", detail=text or error.__class__.__name__)


def format_error_display(error: BaseException | str) -> str:
    display = classify_error(error)
    if display.category == "unknown" and not display.hint:
        return display.detail
    hint = f" Hint: {display.hint}" if display.hint else ""
    return f"{display.category}: {display.detail}{hint}"


def _status_code(error: Any) -> int | None:
    value = getattr(error, "status_code", None)
    if isinstance(value, int):
        return value
    response = getattr(error, "response", None)
    response_value = getattr(response, "status_code", None)
    return response_value if isinstance(response_value, int) else None
