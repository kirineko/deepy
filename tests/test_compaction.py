from __future__ import annotations

import pytest

from deepy.config import ContextConfig, Settings
from deepy.llm.compaction import (
    ContextCompactionError,
    compact_session,
    ensure_context_ready,
    prepare_compaction_items,
)
from deepy.sessions import DeepyJsonlSession
from deepy.usage import TokenUsage


def test_prepare_compaction_items_preserves_recent_messages_and_tool_group():
    items = [
        {"role": "user", "content": "old"},
        {"type": "function_call", "call_id": "call-1", "name": "read", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "call-1", "output": "result"},
        {"role": "assistant", "content": "seen"},
        {"role": "user", "content": "continue"},
    ]

    prepared = prepare_compaction_items(items, preserve_recent_messages=2)

    assert prepared is not None
    to_compact, to_preserve = prepared
    assert to_compact == [{"role": "user", "content": "old"}]
    assert to_preserve[0]["type"] == "function_call"
    assert to_preserve[-1] == {"role": "user", "content": "continue"}


@pytest.mark.asyncio
async def test_compact_session_generates_summary_archives_and_rewrites(monkeypatch, tmp_path):
    async def fake_run_compaction_model(items, settings, *, provider=None, focus_instruction=None):
        assert items == [{"role": "user", "content": "old"}]
        assert focus_instruction == "focus"
        return "<analysis>hidden</analysis><summary>Important summary.</summary>", TokenUsage(
            completion_tokens=3,
            total_tokens=3,
        )

    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", fake_run_compaction_model)
    session = DeepyJsonlSession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
    await session.add_items(
        [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "recent answer"},
            {"role": "user", "content": "recent request"},
        ]
    )

    result = await compact_session(
        session,
        Settings(),
        reason="manual",
        focus_instruction="focus",
    )

    items = await session.get_items()
    assert result.compacted is True
    assert result.archive_path is not None
    assert result.archive_path.exists()
    assert "Important summary." in items[0]["content"]
    assert "hidden" not in items[0]["content"]
    assert items[1:] == [
        {"role": "assistant", "content": "recent answer"},
        {"role": "user", "content": "recent request"},
    ]


@pytest.mark.asyncio
async def test_compact_session_restores_archive_when_rewrite_fails(monkeypatch, tmp_path):
    async def fake_run_compaction_model(items, settings, *, provider=None, focus_instruction=None):
        return "summary", TokenUsage(completion_tokens=1, total_tokens=1)

    async def fail_replace_items(self, items, *, active_tokens=None):
        raise OSError("disk full")

    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", fake_run_compaction_model)
    monkeypatch.setattr("deepy.sessions.jsonl.DeepyJsonlSession.replace_items", fail_replace_items)
    session = DeepyJsonlSession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
    original = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "recent"},
        {"role": "user", "content": "continue"},
    ]
    await session.add_items(original)

    with pytest.raises(ContextCompactionError, match="Failed to write compacted session"):
        await compact_session(session, Settings(), reason="manual")

    restored = await DeepyJsonlSession.open(
        tmp_path,
        "s1",
        deepy_home=tmp_path / "home",
    ).get_items()
    assert restored == original


@pytest.mark.asyncio
async def test_ensure_context_ready_blocks_when_auto_compaction_cannot_fit(tmp_path):
    session = DeepyJsonlSession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
    await session.add_items([{"role": "user", "content": "x" * 1000}])

    with pytest.raises(ContextCompactionError, match="could not be compacted enough"):
        await ensure_context_ready(
            session,
            Settings(
                context=ContextConfig(
                    window_tokens=50,
                    compact_trigger_ratio=0.8,
                    reserved_context_tokens=10,
                )
            ),
            additional_input="continue",
        )
