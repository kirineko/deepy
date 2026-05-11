from __future__ import annotations

from deepy.ui.loading_text import build_loading_text
from deepy.ui.loading_text import format_elapsed_time
from deepy.ui.loading_text import parse_timestamp_ms


STARTED_AT = "2026-04-28T00:00:00.000Z"
STARTED_MS = 1_777_334_400_000


def test_parse_timestamp_ms_handles_iso_z_timestamp():
    assert parse_timestamp_ms(STARTED_AT) == STARTED_MS


def test_build_loading_text_returns_plain_thinking_without_progress():
    assert build_loading_text(progress=None, now_ms=STARTED_MS) == "Thinking..."


def test_build_loading_text_shows_running_process_before_thinking_progress():
    text = build_loading_text(
        processes={"123": {"startTime": STARTED_AT, "command": "yarn install"}},
        progress={
            "requestId": "r",
            "startedAt": STARTED_AT,
            "estimatedTokens": 850,
            "formattedTokens": "850",
            "phase": "update",
        },
        now_ms=STARTED_MS + 5_750,
    )

    assert text == "(5s) yarn install"


def test_build_loading_text_formats_long_running_process_time_with_minutes():
    assert build_loading_text(
        processes={
            "web-search": {
                "startTime": STARTED_AT,
                "command": "WebSearch: latest node release",
            }
        },
        progress=None,
        now_ms=STARTED_MS + 65_250,
    ) == "(1m5s) WebSearch: latest node release"


def test_build_loading_text_returns_plain_thinking_below_stall_threshold():
    text = build_loading_text(
        progress={
            "requestId": "r",
            "startedAt": STARTED_AT,
            "estimatedTokens": 12,
            "formattedTokens": "12",
            "phase": "update",
        },
        now_ms=STARTED_MS + 1_500,
    )

    assert text == "Thinking..."


def test_build_loading_text_shows_elapsed_seconds_and_tokens_after_threshold():
    text = build_loading_text(
        progress={
            "requestId": "r",
            "startedAt": STARTED_AT,
            "estimatedTokens": 850,
            "formattedTokens": "850",
            "phase": "update",
        },
        now_ms=STARTED_MS + 5_750,
    )

    assert text == "Thinking... (5s) · ↓ 850 tokens"


def test_build_loading_text_falls_back_to_zero_tokens_when_missing():
    text = build_loading_text(
        progress={
            "requestId": "r",
            "startedAt": STARTED_AT,
            "estimatedTokens": 0,
            "formattedTokens": "",
            "phase": "update",
        },
        now_ms=STARTED_MS + 4_000,
    )

    assert text == "Thinking... (4s) · ↓ 0 tokens"


def test_build_loading_text_falls_back_to_thinking_for_invalid_timestamp():
    text = build_loading_text(
        progress={
            "requestId": "r",
            "startedAt": "not-a-date",
            "estimatedTokens": 0,
            "formattedTokens": "0",
            "phase": "update",
        },
        now_ms=STARTED_MS,
    )

    assert text == "Thinking..."


def test_format_elapsed_time_handles_invalid_timestamp_as_zero():
    assert format_elapsed_time("not-a-date", now_ms=STARTED_MS) == "0s"
