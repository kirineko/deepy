"""Large valid images must be split before the summary HTTP boundary."""

import base64
from dataclasses import replace

import httpx
import pytest

from deepy.config import Settings
from deepy.llm.cache_context import build_cache_prefix_snapshot
from deepy.llm.compaction import ContextCompactionError
from deepy.llm.history_migration import summarize_bounded, summary_input
from deepy.llm.response_images import validate_encoded_request
from deepy.llm.summary_size import summary_body_fits, summary_instructions
from deepy.sessions import DeepySession
from deepy.usage import TokenUsage


@pytest.fixture
def large_image():
    return {
        "type": "input_image",
        "image_url": "data:image/png;base64," + base64.b64encode(b"x" * (8 * 1024 * 1024)).decode(),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("summary_text", ["Small summary", "description " * 2000])
async def test_large_images_are_split_before_summary_request(tmp_path, large_image, summary_text):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    items = [{"role": "user", "content": [large_image]} for _ in range(3)]
    calls = []

    async def summarize(group, settings, **kwargs):
        value = summary_input(group)
        request = httpx.Request(
            "POST",
            "https://example.test/responses",
            json={
                "input": value,
                "instructions": summary_instructions(None),
                "model": settings.model.name,
                "max_output_tokens": 8192,
            },
        )
        await validate_encoded_request(request)
        calls.append(len(group))
        return summary_text, TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)

    summary, usage = await summarize_bounded(
        items, Settings(), session=session, summarize=summarize
    )
    assert summary == summary_text
    assert calls == [2, 1, 2]  # Two image batches, then merge their text summaries.
    assert usage.total_tokens == 6


@pytest.mark.asyncio
async def test_oversized_tool_group_is_rejected_without_summary_call(tmp_path, large_image):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    items = [
        {"type": "function_call", "call_id": "read", "name": "Read", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "read", "output": [large_image] * 3},
    ]
    await session.add_items(items)

    async def summarize(*args, **kwargs):
        raise AssertionError("An oversized tool group must not reach the summarizer")

    with pytest.raises(ContextCompactionError, match="indivisible"):
        await summarize_bounded(items, Settings(), session=session, summarize=summarize)
    assert await session.get_items() == items


def test_encoded_budget_includes_prefix_tools_focus_and_todo(monkeypatch):
    import deepy.llm.summary_size as sizing

    # Small artificial budget keeps envelope tests fast; real image limits are
    # exercised above without patching the production byte cap.
    monkeypatch.setattr(sizing, "MAX_REQUEST_BYTES", 70 * 1024)
    prefix = build_cache_prefix_snapshot(Settings(), system_instructions="system")
    items = [{"role": "user", "content": "hi"}]
    assert summary_body_fits(summary_input(items), prefix=prefix)
    assert not summary_body_fits(summary_input(items, focus="focus" * 2000), prefix=prefix)
    assert not summary_body_fits(summary_input(items, todo_context="todo" * 2000), prefix=prefix)
    assert not summary_body_fits(
        summary_input(items), prefix=replace(prefix, system_instructions="系" * 3000)
    )
    assert not summary_body_fits(
        summary_input(items), prefix=replace(prefix, tools=({"description": "tool" * 2000},))
    )
    assert not summary_body_fits(
        summary_input(items), prefix=replace(prefix, mcp_tools=({"description": "mcp" * 3000},))
    )
    assert not summary_body_fits(
        summary_input(items), tools=[{"name": "large", "description": "tool" * 2000}]
    )
