from __future__ import annotations


def format_token_count_short(value: int) -> str:
    if value < 1_000:
        return str(value)
    if value < 1_000_000:
        return f"{round(value / 1_000):g}K"
    scaled = value / 1_000_000
    if scaled >= 10:
        return f"{round(scaled):g}M"
    rounded = round(scaled, 1)
    return f"{rounded:g}M"


def format_stream_token_count_short(value: int) -> str:
    if value >= 1_000:
        precision = 1 if value < 100_000 else 0
        formatted = f"{value / 1_000:.{precision}f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return f"{formatted}K"
    return str(value)
