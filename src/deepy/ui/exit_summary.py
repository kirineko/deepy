from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, Mapping

from deepy.session_cost import format_session_cost


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
    session_id: str | None = None,
) -> str:
    usage = extract_usage_fields(_get_usage(session))
    raw_input_suggestion_usage = _get_input_suggestion_usage(session)
    input_suggestion_usage = extract_usage_fields(raw_input_suggestion_usage)
    messages = messages or []
    assistant_count = sum(1 for message in messages if message.get("role") == "assistant")
    resolved_session_id = session_id or _get_session_id(session)
    rows = [
        ("model", model or "unknown"),
        ("session", resolved_session_id or "new"),
        ("messages", _message_summary(messages, assistant_count)),
    ]
    if usage.has_usage:
        rows.append(
            (
                "model usage",
                _usage_summary(
                    usage,
                    requests=assistant_count,
                ),
            )
        )
    if input_suggestion_usage.has_usage:
        rows.append(
            (
                "suggestions",
                _usage_summary(
                    input_suggestion_usage,
                    requests=_get_requests(raw_input_suggestion_usage),
                    model="deepseek-v4-flash",
                ),
            )
        )
    cost = format_session_cost(_get_session_cost(session))
    if cost:
        rows.append(("session cost", cost))
    return _simple_box("Deepy Session Summary", rows)

def _usage_summary(
    usage: UsageFields,
    *,
    requests: int,
    model: str | None = None,
) -> str:
    parts: list[str] = []
    if model:
        parts.append(model)
    if requests > 0:
        parts.append(f"requests {_format_number(requests)}")
    parts.extend(
        [
            f"input {_format_number(usage.prompt_tokens)}",
            f"output {_format_number(usage.completion_tokens)}",
        ]
    )
    if usage.cached_tokens:
        parts.append(f"cached {_format_number(usage.cached_tokens)}")
    if usage.reasoning_tokens:
        parts.append(f"reasoning {_format_number(usage.reasoning_tokens)}")
    return " · ".join(parts)


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


def _get_session_cost(session: Any | None) -> Any:
    if session is None:
        return None
    if isinstance(session, Mapping):
        return session.get("session_cost") or session.get("sessionCost")
    return getattr(session, "session_cost", None)


def _get_session_id(session: Any | None) -> str | None:
    if session is None:
        return None
    value = session.get("id") if isinstance(session, Mapping) else getattr(session, "id", None)
    return value if isinstance(value, str) and value else None


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


def _message_summary(messages: Sequence[Mapping[str, Any]], assistant_count: int) -> str:
    if not messages:
        return "none"
    return f"{len(messages):,} total · {assistant_count:,} assistant"


def _simple_box(title: str, rows: list[tuple[str, str]]) -> str:
    key_width = max(len(key) for key, _ in rows)
    row_texts = [f"{key.ljust(key_width)}  {value}" for key, value in rows]
    width = max(INNER_WIDTH, len(title), *(len(text) for text in row_texts))
    border = "─" * width
    lines = [f"╭{border}╮", _box_line(title, width), f"├{border}┤"]
    for text in row_texts:
        lines.append(_box_line(text, width))
    lines.append(f"╰{border}╯")
    return "\n".join(lines)


def _box_line(text: str, width: int) -> str:
    clipped = text[:width]
    return f"│{clipped.ljust(width)}│"


def _pad_right(text: str, width: int) -> str:
    return text + " " * max(0, width - len(text))
