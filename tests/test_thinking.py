from __future__ import annotations

from deepy.llm.thinking import build_thinking_extra_body


def test_enabled_thinking_uses_reasoning_effort():
    assert build_thinking_extra_body(True, "high") == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }


def test_disabled_thinking_keeps_disabled_payload_without_effort():
    assert build_thinking_extra_body(False, "max") == {
        "thinking": {"type": "disabled"},
    }
