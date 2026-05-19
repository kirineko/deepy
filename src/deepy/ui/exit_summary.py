from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, Mapping


INNER_WIDTH = 98
CONTENT_WIDTH = INNER_WIDTH - 4


@dataclass(frozen=True)
class UsageFields:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def has_usage(self) -> bool:
        return self.prompt_tokens > 0 or self.completion_tokens > 0 or self.reasoning_tokens > 0


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
    completion_details = usage.get("completion_tokens_details")
    output_details = usage.get("output_tokens_details")
    reasoning_tokens = 0
    if isinstance(completion_details, Mapping):
        reasoning_tokens = _number_field(completion_details.get("reasoning_tokens"))
    if reasoning_tokens == 0 and isinstance(output_details, Mapping):
        reasoning_tokens = _number_field(output_details.get("reasoning_tokens"))
    if reasoning_tokens == 0:
        reasoning_tokens = _number_field(usage.get("reasoning_tokens"))

    return UsageFields(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
    )


def build_exit_summary_text(
    *,
    session: Any | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
    model: str | None = None,
) -> str:
    usage = extract_usage_fields(_get_usage(session))
    input_suggestion_usage = extract_usage_fields(_get_input_suggestion_usage(session))
    assistant_count = sum(1 for message in messages or [] if message.get("role") == "assistant")

    rows = [
        "",
        "Goodbye!",
        "",
    ]

    if usage.has_usage:
        rows.extend(
            _usage_rows(
                usage,
                assistant_count=assistant_count,
                model=model or "unknown",
                title="Cumulative Model Usage",
            )
        )
    if input_suggestion_usage.has_usage:
        rows.extend(
            _usage_rows(
                input_suggestion_usage,
                assistant_count=_get_requests(_get_input_suggestion_usage(session)),
                model="deepseek-v4-flash",
                title="Input Suggestion Usage",
            )
        )

    rows.append("")
    body = "\n".join(_box_line(row) for row in rows)
    border = "─" * INNER_WIDTH
    return f"╭{border}╮\n{body}\n╰{border}╯"


def _usage_rows(
    usage: UsageFields,
    *,
    assistant_count: int,
    model: str,
    title: str,
) -> list[str]:
    col_model = 26
    col_reqs = 6
    col_input = 14
    col_output = 14
    col_cached = 14
    col_reasoning = 14
    table_width = col_model + col_reqs + col_input + col_output + col_cached + col_reasoning
    header = (
        _pad_right(title, col_model)
        + _pad_left("Reqs", col_reqs)
        + _pad_left("Input Tokens", col_input)
        + _pad_left("Output Tokens", col_output)
        + _pad_left("Cached Tokens", col_cached)
        + _pad_left("Reasoning", col_reasoning)
    )
    data = (
        _pad_right(model, col_model)
        + _pad_right(str(assistant_count).rjust(col_reqs), col_reqs)
        + _pad_right(_format_number(usage.prompt_tokens).rjust(col_input), col_input)
        + _pad_right(_format_number(usage.completion_tokens).rjust(col_output), col_output)
        + _pad_right(_format_number(usage.cached_tokens).rjust(col_cached), col_cached)
        + _pad_right(_format_number(usage.reasoning_tokens).rjust(col_reasoning), col_reasoning)
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


def _get_input_suggestion_usage(session: Any | None) -> Any:
    if session is None:
        return None
    if isinstance(session, Mapping):
        return session.get("input_suggestion_usage") or session.get("inputSuggestionUsage")
    return getattr(session, "input_suggestion_usage", None)


def _get_requests(usage: Any) -> int:
    if not isinstance(usage, Mapping):
        return 0
    return _number_field(usage.get("requests"))


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
