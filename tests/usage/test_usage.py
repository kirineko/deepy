from __future__ import annotations

from types import SimpleNamespace

from deepy.usage import (
    context_window_usage,
    format_usage_line,
    latest_request_usage,
    merge_usage,
    normalize_usage,
)


def test_normalize_usage_reads_deepseek_chat_completion_fields():
    usage = normalize_usage(
        {
            "prompt_tokens": 11_966,
            "completion_tokens": 236,
            "total_tokens": 12_202,
            "prompt_cache_hit_tokens": 11_776,
            "prompt_cache_miss_tokens": 190,
            "completion_tokens_details": {"reasoning_tokens": 144},
        }
    )

    assert usage.prompt_tokens == 11_966
    assert usage.completion_tokens == 236
    assert usage.total_tokens == 12_202
    assert usage.prompt_cache_hit_tokens == 11_776
    assert usage.prompt_cache_miss_tokens == 190
    assert usage.reasoning_tokens == 144


def test_normalize_usage_reads_openai_agents_sdk_usage_shape():
    usage = normalize_usage(
        SimpleNamespace(
            requests=1,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            input_tokens_details=SimpleNamespace(cached_tokens=4),
            output_tokens_details=SimpleNamespace(reasoning_tokens=3),
        )
    )

    assert usage.requests == 1
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 5
    assert usage.prompt_cache_hit_tokens == 4
    assert usage.reasoning_tokens == 3


def test_merge_usage_and_format_line():
    usage = merge_usage(
        {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18},
    )

    assert usage.prompt_tokens == 9
    assert usage.completion_tokens == 14
    assert usage.total_tokens == 23
    assert format_usage_line(usage) == "input 9 · output 14 · total 23"


def test_format_usage_line_shows_cache_hit_rate():
    usage = normalize_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
        }
    )

    assert (
        format_usage_line(usage)
        == "input 100 · fresh input 20 · cached input 80 (80.0% hit) · output 25 · total 125"
    )


def test_normalize_usage_infers_cache_miss_and_request_entries():
    usage = normalize_usage(
        {
            "input_tokens": 100,
            "output_tokens": 25,
            "input_tokens_details": {"cached_tokens": 80},
            "output_tokens_details": {"reasoning_tokens": 9},
        }
    )

    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 25
    assert usage.total_tokens == 125
    assert usage.prompt_cache_hit_tokens == 80
    assert usage.prompt_cache_miss_tokens == 20
    assert usage.reasoning_tokens == 9
    assert usage.requests == 1
    assert usage.request_usage_entries == [
        {
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
            "reasoning_tokens": 9,
        }
    ]


def test_merge_usage_preserves_request_entries_and_counts():
    usage = merge_usage(
        {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
            "request_usage_entries": [{"prompt_tokens": 10, "completion_tokens": 4}],
        },
        {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
            "requests": 2,
            "request_usage_entries": [
                {"prompt_tokens": 1, "completion_tokens": 1},
                {"prompt_tokens": 2, "completion_tokens": 1},
            ],
        },
    )

    assert usage.prompt_tokens == 13
    assert usage.completion_tokens == 6
    assert usage.total_tokens == 19
    assert usage.requests == 3
    assert len(usage.request_usage_entries) == 3


def test_context_window_usage_uses_prompt_total_without_double_counting_cache():
    usage = normalize_usage(
        {
            "prompt_tokens": 11_966,
            "completion_tokens": 236,
            "total_tokens": 12_202,
            "prompt_cache_hit_tokens": 11_776,
            "prompt_cache_miss_tokens": 190,
            "completion_tokens_details": {"reasoning_tokens": 144},
        }
    )

    context_usage = context_window_usage(usage)

    assert context_usage is not None
    assert context_usage.input_tokens == 11_966
    assert context_usage.output_tokens == 236
    assert context_usage.used_tokens == 12_202


def test_context_window_usage_reads_latest_request_entry():
    usage = merge_usage(
        {"prompt_tokens": 9_000, "completion_tokens": 10, "total_tokens": 9_010},
        {"prompt_tokens": 3_500, "completion_tokens": 10, "total_tokens": 3_510},
    )

    latest = latest_request_usage(usage)
    context_usage = context_window_usage(usage)

    assert latest.prompt_tokens == 3_500
    assert context_usage is not None
    assert context_usage.used_tokens == 3_510
