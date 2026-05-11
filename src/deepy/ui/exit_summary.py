from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


INNER_WIDTH = 98
CONTENT_WIDTH = INNER_WIDTH - 4


@dataclass(frozen=True)
class UsageFields:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0

    @property
    def has_usage(self) -> bool:
        return self.prompt_tokens > 0 or self.completion_tokens > 0


def extract_usage_fields(usage: Any) -> UsageFields:
    if not isinstance(usage, Mapping):
        return UsageFields()

    prompt_tokens = _number_field(usage.get("prompt_tokens"))
    completion_tokens = _number_field(usage.get("completion_tokens"))
    cached_tokens = 0

    prompt_details = usage.get("prompt_tokens_details")
    if isinstance(prompt_details, Mapping):
        cached_tokens = _number_field(prompt_details.get("cached_tokens"))

    if cached_tokens == 0:
        cached_tokens = _number_field(usage.get("prompt_cache_hit_tokens"))

    return UsageFields(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
    )


def build_exit_summary_text(
    *,
    session: Any | None = None,
    messages: list[Mapping[str, Any]] | None = None,
    model: str | None = None,
) -> str:
    usage = extract_usage_fields(_get_usage(session))
    assistant_count = sum(1 for message in messages or [] if message.get("role") == "assistant")

    rows = [
        "",
        "Goodbye!",
        "",
    ]

    if usage.has_usage:
        rows.extend(_usage_rows(usage, assistant_count=assistant_count, model=model or "unknown"))

    rows.append("")
    body = "\n".join(_box_line(row) for row in rows)
    border = "─" * INNER_WIDTH
    return f"╭{border}╮\n{body}\n╰{border}╯"


def _usage_rows(usage: UsageFields, *, assistant_count: int, model: str) -> list[str]:
    col_model = 34
    col_reqs = 8
    col_input = 16
    col_output = 16
    col_cached = 18
    table_width = col_model + col_reqs + col_input + col_output + col_cached
    header = (
        _pad_right("Model Usage", col_model)
        + _pad_left("Reqs", col_reqs)
        + _pad_left("Input Tokens", col_input)
        + _pad_left("Output Tokens", col_output)
        + _pad_left("Cached Tokens", col_cached)
    )
    data = (
        _pad_right(model, col_model)
        + _pad_right(str(assistant_count).rjust(col_reqs), col_reqs)
        + _pad_right(_format_number(usage.prompt_tokens).rjust(col_input), col_input)
        + _pad_right(_format_number(usage.completion_tokens).rjust(col_output), col_output)
        + _pad_right(_format_number(usage.cached_tokens).rjust(col_cached), col_cached)
    )
    return [
        header,
        "─" * table_width,
        data,
        "",
    ]


def _get_usage(session: Any | None) -> Any:
    if session is None:
        return None
    if isinstance(session, Mapping):
        return session.get("usage")
    return getattr(session, "usage", None)


def _number_field(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0


def _format_number(value: int) -> str:
    return f"{value:,}"


def _box_line(text: str) -> str:
    return f"│  {_pad_right(text, CONTENT_WIDTH)}  │"


def _pad_right(text: str, width: int) -> str:
    return text + " " * max(0, width - len(text))


def _pad_left(text: str, width: int) -> str:
    return " " * max(0, width - len(text)) + text
