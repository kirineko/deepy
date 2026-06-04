from __future__ import annotations

import pytest

from deepy.config import ContextConfig, Settings
from deepy.llm.compaction import (
    ContextCompactionError,
    compact_session,
    ensure_context_ready,
    prepare_compaction_items,
    run_compaction_model,
)
from deepy.llm.cache_context import build_cache_prefix_snapshot
from deepy.llm.provider import ProviderBundle
from agents import ModelSettings
from deepy.sessions import DeepySession, list_session_entries
from deepy.usage import TokenUsage


def test_prepare_compaction_items_preserves_recent_messages_and_tool_group():
    items = [
        {"role": "user", "content": "old"},
        {"type": "function_call", "call_id": "call-1", "name": "Read", "arguments": "{}"},
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
async def test_run_compaction_model_uses_active_model_settings_and_prefix(monkeypatch):
    captured = {}

    class FakeRunner:
        @staticmethod
        async def run(agent, prompt, max_turns, run_config):
            captured["model"] = getattr(agent.model, "model", agent.model)
            captured["settings"] = agent.model_settings
            captured["instructions"] = agent.instructions
            captured["tools"] = agent.tools
            captured["prompt"] = prompt
            return type("Result", (), {"final_output": "<summary>summary</summary>"})()

    monkeypatch.setattr("agents.Runner", FakeRunner)
    settings = Settings()
    prefix = build_cache_prefix_snapshot(settings, system_instructions="stable prefix")
    tool = object()
    active_settings = ModelSettings(include_usage=True, store=False)

    summary, usage = await run_compaction_model(
        [{"role": "user", "content": "old"}],
        settings,
        provider=ProviderBundle(client=object(), model="active-model", model_settings=active_settings),
        prefix_snapshot=prefix,
        prefix_tools=[tool],
    )

    assert summary == "<summary>summary</summary>"
    assert usage.known is False
    assert captured["model"] == "active-model"
    assert captured["settings"] is active_settings
    assert "stable prefix" in captured["instructions"]
    assert captured["tools"] == [tool]
    assert captured["prompt"].index("```jsonl") < captured["prompt"].index("Your task is")


@pytest.mark.asyncio
async def test_compact_session_generates_summary_archives_and_rewrites(monkeypatch, tmp_path):
    async def fake_run_compaction_model(
        items,
        settings,
        *,
        provider=None,
        focus_instruction=None,
        todo_state=None,
    ):
        assert items == [{"role": "user", "content": "old"}]
        assert focus_instruction == "focus"
        assert todo_state == [
            {"id": "one", "content": "Continue implementation", "status": "in_progress"}
        ]
        return "<analysis>hidden</analysis><summary>Important summary.</summary>", TokenUsage(
            completion_tokens=3,
            total_tokens=3,
        )

    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", fake_run_compaction_model)
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
    await session.add_items(
        [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "recent answer"},
            {"role": "user", "content": "recent request"},
        ]
    )
    session._touch_index(
        active_tokens=87_058,
        latest_context_window_tokens=24_000,
        last_usage_tokens=87_058,
        pending_tokens=0,
        last_usage_record_count=3,
        todo_state=[{"id": "one", "content": "Continue implementation", "status": "in_progress"}],
    )

    result = await compact_session(
        session,
        Settings(),
        reason="manual",
        focus_instruction="focus",
    )

    items = await session.get_items()
    assert result.compacted is True
    assert result.before_tokens == 24_000
    assert result.archive_id is not None
    assert "Important summary." in items[0]["content"]
    assert "hidden" not in items[0]["content"]
    assert items[1:] == [
        {"role": "assistant", "content": "recent answer"},
        {"role": "user", "content": "recent request"},
    ]
    entry = list_session_entries(tmp_path, deepy_home=tmp_path / "home")[0]
    assert entry.latest_context_window_tokens == result.after_tokens
    assert session.latest_context_window_usage() is not None
    assert session.latest_context_window_usage().used_tokens == result.after_tokens
    assert session.todo_state() == [
        {"id": "one", "content": "Continue implementation", "status": "in_progress"}
    ]
    cache_state = session.cache_context_state()
    assert cache_state.prefix_generation == 1
    assert cache_state.cache_break_reason == "history rewritten: manual compaction"


@pytest.mark.asyncio
async def test_compact_session_restores_archive_when_rewrite_fails(monkeypatch, tmp_path):
    async def fake_run_compaction_model(
        items,
        settings,
        *,
        provider=None,
        focus_instruction=None,
        todo_state=None,
    ):
        return "summary", TokenUsage(completion_tokens=1, total_tokens=1)

    async def fail_archive_and_replace_items(
        self, items, *, active_tokens, reason, before_tokens, after_tokens
    ):
        raise OSError("disk full")

    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", fake_run_compaction_model)
    monkeypatch.setattr(
        "deepy.sessions.session.DeepySession.archive_and_replace_items",
        fail_archive_and_replace_items,
    )
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
    original = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "recent"},
        {"role": "user", "content": "continue"},
    ]
    await session.add_items(original)

    with pytest.raises(ContextCompactionError, match="Failed to write compacted session"):
        await compact_session(session, Settings(), reason="manual")

    restored = await DeepySession.open(
        tmp_path,
        "s1",
        deepy_home=tmp_path / "home",
    ).get_items()
    assert restored == original


@pytest.mark.asyncio
async def test_ensure_context_ready_blocks_when_auto_compaction_cannot_fit(tmp_path):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
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


@pytest.mark.asyncio
async def test_ensure_context_ready_does_not_compact_after_short_latest_context_usage(
    monkeypatch,
    tmp_path,
):
    compact_calls = 0

    async def fake_compact_session(session, settings, *, provider=None, reason):
        nonlocal compact_calls
        compact_calls += 1
        return type(
            "FakeCompaction",
            (),
            {
                "compacted": True,
                "before_tokens": session.context_token_state().active_tokens,
                "after_tokens": 100,
            },
        )()

    monkeypatch.setattr("deepy.llm.compaction.compact_session", fake_compact_session)
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
    await session.add_items([{"role": "user", "content": "large prompt"}])
    session.record_usage({"prompt_tokens": 900, "completion_tokens": 5, "total_tokens": 905})
    await session.add_items(
        [{"role": "assistant", "content": "answer"}, {"role": "user", "content": "hi"}]
    )
    session.record_usage({"prompt_tokens": 20, "completion_tokens": 2, "total_tokens": 22})

    readiness = await ensure_context_ready(
        session,
        Settings(
            context=ContextConfig(
                window_tokens=1_000,
                compact_trigger_ratio=0.8,
                reserved_context_tokens=50,
            )
        ),
        additional_input="continue",
    )

    assert compact_calls == 0
    assert readiness.compacted is False
    assert readiness.before_tokens >= 900


@pytest.mark.asyncio
async def test_ensure_context_ready_compacts_when_latest_context_usage_reaches_threshold(
    monkeypatch,
    tmp_path,
):
    compact_calls = 0

    async def fake_compact_session(session, settings, *, provider=None, reason):
        nonlocal compact_calls
        compact_calls += 1
        await session.replace_items([{"role": "user", "content": "summary"}], active_tokens=100)
        return type(
            "FakeCompaction",
            (),
            {
                "compacted": True,
                "before_tokens": 850,
                "after_tokens": 100,
            },
        )()

    monkeypatch.setattr("deepy.llm.compaction.compact_session", fake_compact_session)
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home", session_id="s1")
    await session.add_items([{"role": "user", "content": "large prompt"}])
    session.record_usage({"prompt_tokens": 850, "completion_tokens": 5, "total_tokens": 855})

    readiness = await ensure_context_ready(
        session,
        Settings(
            context=ContextConfig(
                window_tokens=1_000,
                compact_trigger_ratio=0.8,
                reserved_context_tokens=50,
            )
        ),
        additional_input="continue",
    )

    assert compact_calls == 1
    assert readiness.compacted is True
    latest_usage = session.latest_context_window_usage()
    assert latest_usage is not None
    assert latest_usage.used_tokens == 100
