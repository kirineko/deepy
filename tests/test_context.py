from __future__ import annotations

from deepy.config.settings import ContextConfig, Settings
from deepy.llm.context import (
    build_session_input_callback,
    estimate_tokens_for_item,
    should_auto_compact,
)
from deepy.prompts import build_compact_prompt
from deepy.prompts.compact import build_compact_summary_message, strip_compact_analysis


def test_session_input_callback_does_not_trim_or_compact():
    settings = Settings(context=ContextConfig(window_tokens=100, compact_trigger_ratio=0.5))
    callback = build_session_input_callback(settings)
    history = [{"role": "assistant", "content": "x" * 100} for _ in range(10)]
    new_input = [{"role": "user", "content": "continue"}]

    prepared = callback(history, new_input)

    assert prepared == history + new_input


def test_should_auto_compact_uses_ratio_or_reserved_context():
    assert should_auto_compact(850, 1000, trigger_ratio=0.8, reserved_context_size=50)
    assert should_auto_compact(760, 1000, trigger_ratio=0.8, reserved_context_size=250)
    assert not should_auto_compact(700, 1000, trigger_ratio=0.8, reserved_context_size=50)
    assert not should_auto_compact(0, 1000, trigger_ratio=0.8, reserved_context_size=50)


def test_token_estimate_counts_tool_call_arguments():
    with_arguments = estimate_tokens_for_item(
        {
            "type": "function_call",
            "name": "write_file",
            "call_id": "call-1",
            "arguments": '{"file_path":"big.py","content":"' + ("x" * 2000) + '"}',
        }
    )
    without_arguments = estimate_tokens_for_item(
        {
            "type": "function_call",
            "name": "write_file",
            "call_id": "call-1",
            "arguments": "{}",
        }
    )

    assert with_arguments > without_arguments
    assert with_arguments > 100


def test_build_compact_prompt_serializes_session_messages_as_jsonl_and_focus():
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
        ],
        focus_instruction="focus on file paths",
    )

    assert "Your task is to create a detailed summary" in prompt
    assert "focus on file paths" in prompt
    assert "conversation below:" in prompt
    assert '```jsonl\n{"id":"m1","role":"user","content":"请继续"' in prompt
    assert '"tool_call_id":"call-1"' in prompt
    assert '"created_at":123' in prompt
    assert "ignored" not in prompt


def test_compact_summary_message_strips_analysis_wrapper():
    message = build_compact_summary_message(
        "<analysis>hidden</analysis><summary>Keep this state.</summary>"
    )

    assert message["role"] == "user"
    assert "hidden" not in message["content"]
    assert "Keep this state." in message["content"]
    assert strip_compact_analysis("<summary>ok</summary>") == "ok"
