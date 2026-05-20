from __future__ import annotations

from deepy.ui.exit_summary import build_exit_summary_text
from deepy.ui.exit_summary import extract_usage_fields


def test_extract_usage_fields_reads_cached_tokens_from_details():
    usage = extract_usage_fields(
        {
            "prompt_tokens": 11_966,
            "completion_tokens": 236,
            "total_tokens": 12_202,
            "prompt_tokens_details": {"cached_tokens": 11_776},
            "completion_tokens_details": {"reasoning_tokens": 144},
        }
    )

    assert usage.prompt_tokens == 11_966
    assert usage.completion_tokens == 236
    assert usage.cached_tokens == 11_776
    assert usage.reasoning_tokens == 144


def test_extract_usage_fields_falls_back_to_prompt_cache_hit_tokens():
    usage = extract_usage_fields(
        {
            "prompt_tokens": 20,
            "completion_tokens": 7,
            "prompt_cache_hit_tokens": 11,
        }
    )

    assert usage.cached_tokens == 11


def test_build_exit_summary_text_shows_usage_and_reasoning_tokens():
    summary = build_exit_summary_text(
        session={
            "usage": {
                "prompt_tokens": 11_966,
                "completion_tokens": 236,
                "prompt_tokens_details": {"cached_tokens": 11_776},
                "completion_tokens_details": {"reasoning_tokens": 144},
            }
        },
        messages=[
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "hello"},
        ],
        model="mimo-v2.5-pro",
        session_id="s1",
    )

    assert "Deepy Session Summary" in summary
    assert "╭" in summary
    assert "╰" in summary
    assert "model usage" in summary
    assert "cached" in summary
    assert "reasoning" in summary
    assert "mimo-v2.5-pro" in summary
    assert "session" in summary
    assert "s1" in summary
    assert "11,966" in summary
    assert "11,776" in summary
    assert "144" in summary
    assert "Agent powering down" not in summary
    assert "Interaction Summary" not in summary
    assert "Context Window" not in summary
    assert "balance" not in summary.lower()


def test_build_exit_summary_text_omits_usage_table_without_usage():
    summary = build_exit_summary_text(model="deepseek-v4-pro")

    assert "Deepy Session Summary" in summary
    assert "model" in summary
    assert "deepseek-v4-pro" in summary
    assert "model usage" not in summary


def test_build_exit_summary_text_shows_input_suggestion_usage_separately():
    summary = build_exit_summary_text(
        session={
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
            "inputSuggestionUsage": {
                "prompt_tokens": 12,
                "completion_tokens": 3,
                "total_tokens": 15,
                "requests": 2,
            },
        },
        messages=[
            {"role": "assistant", "content": "one"},
            {"role": "assistant", "content": "two"},
        ],
        model="deepseek-v4-pro",
    )

    assert "model usage" in summary
    assert "suggestions" in summary
    assert "deepseek-v4-flash" in summary
    assert "12" in summary
    assert "3" in summary


def test_build_exit_summary_text_shows_session_cost_delta():
    summary = build_exit_summary_text(
        session={
            "sessionCost": {
                "attempted": True,
                "amounts": [
                    {
                        "currency": "CNY",
                        "startTotal": "100.00",
                        "endTotal": "99.75",
                        "spent": "0.25",
                    }
                ],
            }
        },
        model="deepseek-v4-pro",
    )

    assert "session cost" in summary
    assert "CNY 0.25" in summary
    assert "DeepSeek balance delta" in summary


def test_build_exit_summary_text_shows_unavailable_session_cost():
    summary = build_exit_summary_text(
        session={"sessionCost": {"attempted": True, "unavailableReason": "end timeout"}},
        model="deepseek-v4-pro",
    )

    assert "session cost" in summary
    assert "unavailable (end timeout)" in summary
