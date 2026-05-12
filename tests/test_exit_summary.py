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
    )

    assert "Goodbye!" in summary
    assert "╭" in summary
    assert "╰" in summary
    assert "Cumulative Model Usage" in summary
    assert "Cached Tokens" in summary
    assert "Reasoning" in summary
    assert "mimo-v2.5-pro" in summary
    assert "11,966" in summary
    assert "11,776" in summary
    assert "144" in summary
    assert "Agent powering down" not in summary
    assert "Interaction Summary" not in summary
    assert "Context Window" not in summary


def test_build_exit_summary_text_omits_usage_table_without_usage():
    summary = build_exit_summary_text(model="deepseek-v4-pro")

    assert "Goodbye!" in summary
    assert "Cumulative Model Usage" not in summary
