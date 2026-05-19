from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from deepy.config import ModelConfig, Settings
from deepy.input_suggestions import (
    INPUT_SUGGESTION_MODEL,
    InputSuggestionController,
    assistant_reply_count,
    generate_input_suggestion,
    get_filter_reason,
    input_suggestion_model_settings,
    is_eligible_for_input_suggestion,
    parse_suggestion_text,
    recent_suggestion_messages,
)


def test_input_suggestion_controller_accepts_and_clears_state():
    controller = InputSuggestionController(enabled=True)

    controller.set_suggestion("run tests")

    assert controller.state.visible is True
    assert controller.accept("tab") == "run tests"
    assert controller.last_accepted_method == "tab"
    assert controller.state.visible is False
    assert controller.state.text == "run tests"

    controller.reveal()

    assert controller.accept("right") == "run tests"
    assert controller.last_accepted_method == "right"


def test_input_suggestion_controller_clears_when_disabled():
    controller = InputSuggestionController(enabled=True)
    controller.set_suggestion("run tests")

    controller.set_enabled(False)
    controller.set_suggestion("commit")

    assert controller.enabled is False
    assert controller.state.text is None


def test_input_suggestion_controller_hides_and_reveals_without_losing_text():
    controller = InputSuggestionController(enabled=True)
    controller.set_suggestion("run tests")

    controller.hide()

    assert controller.state.visible is False
    assert controller.state.text == "run tests"

    controller.reveal()

    assert controller.state.visible is True
    assert controller.state.text == "run tests"


@pytest.mark.asyncio
async def test_input_suggestion_delayed_visibility_can_be_cancelled(monkeypatch):
    controller = InputSuggestionController(enabled=True)
    monkeypatch.setattr("deepy.input_suggestions.INPUT_SUGGESTION_DELAY_SECONDS", 0.01)

    task = asyncio.create_task(controller.set_suggestion_after_delay("run tests"))
    await asyncio.sleep(0)
    controller.dismiss()
    await task

    assert controller.state.text is None


def test_input_suggestion_eligibility_requires_two_assistant_replies_and_idle_state():
    items = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]

    assert assistant_reply_count(items) == 1
    assert not is_eligible_for_input_suggestion(items, enabled=True)

    items.append({"type": "model", "output": "four"})

    assert assistant_reply_count(items) == 2
    assert is_eligible_for_input_suggestion(items, enabled=True)
    assert not is_eligible_for_input_suggestion(items, enabled=False)
    assert not is_eligible_for_input_suggestion(items, enabled=True, idle=False)
    assert not is_eligible_for_input_suggestion(items, enabled=True, has_pending_questions=True)
    assert not is_eligible_for_input_suggestion(items, enabled=True, turn_status="failed")


def test_recent_suggestion_messages_keeps_user_and_assistant_context_only():
    items = [
        {"type": "function_call", "name": "shell"},
        {"role": "user", "content": "hello"},
        {"type": "model", "output": "hi"},
        {"role": "assistant", "content": [{"text": "done"}]},
    ]

    assert recent_suggestion_messages(items) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "assistant", "content": "done"},
    ]


def test_input_suggestion_filters_reject_bad_shapes_and_allow_short_commands():
    assert get_filter_reason("continue") is None
    assert get_filter_reason("/status") is None
    assert get_filter_reason("继续") is None
    assert get_filter_reason("Suggestion: run tests") == "prefixed_label"
    assert get_filter_reason("looks good") == "evaluative"
    assert get_filter_reason("I can run tests") == "ai_voice"
    assert get_filter_reason("run tests\nthen commit") == "has_formatting"
    assert get_filter_reason("Run tests. Commit changes") == "multiple_sentences"
    assert get_filter_reason("why?") == "question"
    assert get_filter_reason("x") == "too_few_words"


def test_parse_suggestion_text_supports_plain_and_json_payloads():
    assert parse_suggestion_text('"run focused tests"') == "run focused tests"
    assert parse_suggestion_text('{"suggestion": "run focused tests"}') == "run focused tests"
    assert parse_suggestion_text('{"suggestion": 1}') == ""


def test_input_suggestion_model_settings_are_fixed_deepseek_flash_non_thinking():
    settings = input_suggestion_model_settings()

    assert INPUT_SUGGESTION_MODEL == "deepseek-v4-flash"
    assert settings.include_usage is True
    assert settings.store is False
    assert settings.extra_body == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in settings.extra_body


@pytest.mark.asyncio
async def test_generate_input_suggestion_uses_fixed_model_and_records_usage(monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="run tests"))],
                usage=SimpleNamespace(prompt_tokens=9, completion_tokens=2, total_tokens=11),
            )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            calls.append({"client": kwargs})
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("deepy.input_suggestions.AsyncOpenAI", FakeAsyncOpenAI)
    settings = Settings(model=ModelConfig(api_key="sk-test", base_url="https://api.example/v1"))
    items = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "next?"},
        {"role": "assistant", "content": "try running tests"},
    ]

    suggestion = await generate_input_suggestion(settings, items, timeout_seconds=1)

    assert suggestion is not None
    assert suggestion.text == "run tests"
    assert suggestion.usage.prompt_tokens == 9
    assert suggestion.usage.completion_tokens == 2
    assert calls[0] == {"client": {"base_url": "https://api.example/v1", "api_key": "sk-test"}}
    assert calls[1]["model"] == "deepseek-v4-flash"
    assert calls[1]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert calls[1]["store"] is False
    assert "reasoning_effort" not in calls[1]


@pytest.mark.asyncio
async def test_generate_input_suggestion_returns_none_without_api_key_or_for_filtered_text():
    no_key = Settings(model=ModelConfig(api_key=""))

    assert await generate_input_suggestion(no_key, [{"role": "assistant", "content": "x"}]) is None
