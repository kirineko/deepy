from __future__ import annotations

from deepy.config.settings import ContextConfig, Settings
from deepy.llm.context import (
    build_session_input_callback,
    compact_items_for_context,
    estimate_tokens_for_item,
    estimate_tokens_for_items,
)
from deepy.prompts import build_compact_prompt


def test_context_callback_keeps_history_under_threshold():
    history = [{"role": "user", "content": "a" * 100} for _ in range(20)]
    new_input = [{"role": "user", "content": "current"}]

    compacted = compact_items_for_context(history, new_input, threshold_tokens=120)

    assert compacted[0]["role"] == "system"
    assert "compacted by Deepy" in compacted[0]["content"]
    assert compacted[-1] == new_input[0]
    assert len(compacted) < len(history) + len(new_input)
    assert estimate_tokens_for_items(compacted) <= 120


def test_context_callback_returns_original_when_under_threshold():
    history = [{"role": "user", "content": "small"}]
    new_input = [{"role": "user", "content": "current"}]

    compacted = compact_items_for_context(history, new_input, threshold_tokens=10_000)

    assert compacted == history + new_input


def test_session_input_callback_uses_resolved_settings_threshold():
    settings = Settings(context=ContextConfig(window_tokens=100, compact_trigger_ratio=0.5))
    callback = build_session_input_callback(settings)
    history = [{"role": "assistant", "content": "x" * 100} for _ in range(10)]
    new_input = [{"role": "user", "content": "continue"}]

    compacted = callback(history, new_input)

    assert compacted[0]["role"] == "system"
    assert compacted[-1] == new_input[0]


def test_token_estimate_counts_tool_call_arguments():
    with_arguments = estimate_tokens_for_item(
        {
            "type": "function_call",
            "name": "write",
            "call_id": "call-1",
            "arguments": '{"file_path":"big.py","content":"' + ("x" * 2000) + '"}',
        }
    )
    without_arguments = estimate_tokens_for_item(
        {
            "type": "function_call",
            "name": "write",
            "call_id": "call-1",
            "arguments": "{}",
        }
    )

    assert with_arguments > without_arguments
    assert with_arguments > 100


def test_build_compact_prompt_serializes_session_messages_as_jsonl():
    prompt = build_compact_prompt(
        [
            {
                "id": "m1",
                "role": "user",
                "content": "请继续",
                "tool_call_id": "call-1",
                "created_at": 123,
                "ignored": "not included",
            }
        ]
    )

    assert "Your task is to create a detailed summary" in prompt
    assert "conversation below:" in prompt
    assert '```jsonl\n{"id":"m1","role":"user","content":"请继续"' in prompt
    assert '"tool_call_id":"call-1"' in prompt
    assert '"created_at":123' in prompt
    assert "ignored" not in prompt
