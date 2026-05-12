from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from deepy.usage import format_usage_line, normalize_usage


STALL_THRESHOLD_MS = 3_000


def build_loading_text(
    *,
    progress: Any | None,
    now_ms: int | float,
    processes: Mapping[str, Any] | None = None,
    usage: Any | None = None,
) -> str:
    usage_suffix = _usage_suffix(usage)
    process_text = build_process_loading_text(processes, now_ms=now_ms)
    if process_text:
        return f"{process_text}{usage_suffix}"

    if progress is None:
        return f"Thinking...{usage_suffix}"

    started_at = parse_timestamp_ms(_field(progress, "startedAt"))
    if started_at is None:
        return f"Thinking...{usage_suffix}"

    elapsed_ms = max(0, int(now_ms - started_at))
    if elapsed_ms < STALL_THRESHOLD_MS:
        return f"Thinking...{usage_suffix}"

    elapsed_seconds = elapsed_ms // 1_000
    tokens = _field(progress, "formattedTokens") or "0"
    return f"Thinking... ({elapsed_seconds}s) · ↓ {tokens} tokens{usage_suffix}"


def build_process_loading_text(
    processes: Mapping[str, Any] | None,
    *,
    now_ms: int | float,
) -> str | None:
    if not processes:
        return None
    first = next(iter(processes.values()), None)
    if first is None:
        return None
    start_time = _field(first, "startTime") or ""
    command = _field(first, "command") or "Running process..."
    return f"({format_elapsed_time(start_time, now_ms=now_ms)}) {command}"


def format_elapsed_time(start_time_iso: str, *, now_ms: int | float) -> str:
    start_time = parse_timestamp_ms(start_time_iso)
    elapsed_ms = 0 if start_time is None else max(0, int(now_ms - start_time))
    elapsed_seconds = elapsed_ms // 1_000
    minutes = elapsed_seconds // 60
    seconds = elapsed_seconds % 60
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def parse_timestamp_ms(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return int(parsed.timestamp() * 1_000)


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _usage_suffix(usage: Any | None) -> str:
    normalized = normalize_usage(usage)
    if not normalized.known:
        return ""
    return f" · {format_usage_line(normalized)}"
