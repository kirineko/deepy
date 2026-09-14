from copy import deepcopy
from dataclasses import replace

import pytest
from agents.exceptions import ModelBehaviorError

from deepy.config import Settings
from deepy.config.model_limits import resolve_model_limits
from deepy.llm.history_projection import project_history, history_groups, model_identity
from deepy.llm.request_budget import request_budget, check_request, RequestBudgetError, estimate_request_value
from deepy.llm.history_migration import summarize_bounded
from deepy.llm.compaction import ContextCompactionError, compact_session, ensure_context_ready
from deepy.llm.cache_context import build_cache_prefix_snapshot
from deepy.sessions import DeepySession
from deepy.sessions.history_state import read_history_state, record_checkpoint
from deepy.usage import TokenUsage


def test_output_reserve_not_double_counted_and_complete_prefix_counted():
    limits = resolve_model_limits("deepseek", "deepseek-flash")
    payload = {"input": "hello", "instructions": "system", "tools": [{"name": "mcp_tool", "parameters": {"query": "text"}}]}
    budget = request_budget(payload, limits)
    assert budget.reserve_tokens == 50_000
    assert budget.input_tokens > request_budget({"input": "hello"}, limits).input_tokens
    assert not replace(budget, input_tokens=950_000).fits
    assert replace(budget, input_tokens=949_999).fits
    assert replace(budget, input_tokens=800_000).needs_compaction(.8)


def test_base64_is_estimated_as_image_and_compact_input_keeps_real_images():
    image = {"type": "input_image", "image_url": "data:image/png;base64," + "A" * 200000}
    assert estimate_request_value(image) == 1024
    # The summary sends image parts, never a base64 transcript string.
    items = [{"role": "user", "content": [{"type": "input_text", "text": "Describe"}, image]}]
    # normalize validates bytes; use the already-tested valid pixel fixture below instead.
    assert estimate_request_value(items) < 1100


@pytest.mark.parametrize("origin", [None, model_identity("deepseek", "other", "https://api.deepseek.com"),
                                    model_identity("kimi", "kimi-k3", "https://api.moonshot.cn/v1")])
def test_reasoning_does_not_cross_model_or_endpoint_or_missing_origin(origin):
    target = model_identity("deepseek", "deepseek-flash", "https://api.deepseek.com")
    items = [{"type": "reasoning", "encrypted_content": "opaque", "deepy_origin": origin},
             {"role": "assistant", "content": "answer"}]
    original = deepcopy(items)
    assert project_history(items, target) == [items[1]]
    assert items == original
    items[0]["deepy_origin"] = target
    assert len(project_history(items, target)) == 2
    assert "deepy_origin" not in project_history(items, target)[0]


def tool_items():
    return [{"type": "function_call", "call_id": "a", "name": "Read", "arguments": "{}"},
            {"type": "function_call", "call_id": "b", "name": "Read", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "b", "output": "b"},
            {"type": "function_call_output", "call_id": "a", "output": "a"}]


def test_parallel_tool_group_is_indivisible_and_incomplete_is_error():
    assert history_groups(tool_items()) == [tool_items()]
    with pytest.raises(ModelBehaviorError, match="Unfinished"):
        history_groups(tool_items()[:-1])
    with pytest.raises(ModelBehaviorError, match="Unpaired"):
        history_groups([tool_items()[-1]])


@pytest.mark.asyncio
async def test_checkpoint_adds_uncovered_input_and_cross_model_downgrades(tmp_path):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    settings = Settings()
    prefix = build_cache_prefix_snapshot(settings, system_instructions="system")
    await session.add_items([{"role": "user", "content": "hello"}])
    session.record_usage({"input_tokens": 4000, "output_tokens": 100})
    record_checkpoint(session, settings, prefix.fingerprint)
    ready = await ensure_context_ready(session, settings, prefix_snapshot=prefix, additional_input="new input " * 300)
    assert ready.before_tokens > 4100
    other = Settings.from_mapping({"active_provider": "mimo"})
    moved = await ensure_context_ready(session, other, prefix_snapshot=prefix, additional_input="new")
    assert moved.before_tokens < 100
    await session.add_items([{"role": "user", "content": "pending " * 200}])
    resumed = DeepySession.open(tmp_path, session.session_id, deepy_home=tmp_path / "home")
    ready = await ensure_context_ready(resumed, settings, prefix_snapshot=prefix, additional_input="new")
    assert ready.before_tokens > 4100


@pytest.mark.asyncio
async def test_revision_failure_keeps_originals_and_counts_successful_summary(tmp_path, monkeypatch):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    originals = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "recent"}, {"role": "user", "content": "new"}]
    await session.add_items(originals)
    async def summarize(*args, **kwargs):
        await session.add_items([{"role": "user", "content": "concurrent"}])
        return "summary", TokenUsage(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", summarize)
    with pytest.raises(ContextCompactionError, match="History changed"):
        await compact_session(session, Settings(), reason="manual")
    assert (await session.get_items())[:3] == originals
    assert read_history_state(session)["summary_usage"]["total_tokens"] == 12
    assert "projection" not in read_history_state(session)


@pytest.mark.asyncio
async def test_migration_failure_or_cancellation_never_replaces_history(tmp_path, monkeypatch):
    import asyncio
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    originals = [{"role": "user", "content": str(i)} for i in range(3)]
    await session.add_items(originals)
    async def fail(*args, **kwargs):
        raise asyncio.CancelledError
    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", fail)
    with pytest.raises(asyncio.CancelledError):
        await compact_session(session, Settings(), reason="manual")
    assert await session.get_items() == originals
    assert "projection" not in read_history_state(session)


@pytest.mark.asyncio
async def test_unknown_checkpoint_is_not_precision(tmp_path):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    await session.add_items([{"role": "user", "content": "short"}])
    session.record_usage({"input_tokens": 999999, "output_tokens": 1})
    assert (await ensure_context_ready(session, Settings())).before_tokens < 100
    assert read_history_state(session) == {}


@pytest.mark.asyncio
async def test_indivisible_group_rejected_before_any_paid_call(tmp_path):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    settings = Settings.from_mapping({"context": {"window_tokens": 60000}})
    calls = []
    async def summarize(*args, **kwargs):
        calls.append(1)
        return "summary", TokenUsage()
    with pytest.raises(ContextCompactionError, match="indivisible"):
        await summarize_bounded([{"role": "user", "content": "many " * 20000}], settings,
                                session=session, summarize=summarize)
    assert not calls


def test_boundary_error_carries_recoverable_history():
    limits = resolve_model_limits("deepseek", "deepseek-flash", global_cap=60000)
    items = [{"role": "user", "content": "many " * 20000}]
    with pytest.raises(RequestBudgetError) as exc:
        check_request({"input": items}, limits)
    assert exc.value.items == items


@pytest.mark.asyncio
async def test_image_reduction_requires_opt_in_and_uses_only_last_source(tmp_path):
    from deepy.llm.history_migration import summary_input
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    image = {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2U="}
    items = [{"role": "user", "content": [image]}]
    await session.add_items(items)
    settings = Settings.from_mapping({"active_provider": "mimo", "providers": {
        "mimo": {"model": "mimo-v2.5-pro"}, "deepseek": {"api_key": "test"}}})
    calls, announcements = [], []
    async def summarize(group, candidate, **kwargs):
        calls.append(candidate.model.name)
        if candidate.model.provider == "deepseek":
            wire = summary_input(group)
            assert wire[0]["content"][1] == image
            assert "base64" not in wire[0]["content"][0]["text"]
        return "A text description", TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    with pytest.raises(ContextCompactionError, match="explicitly"):
        await summarize_bounded(items, settings, session=session, summarize=summarize)
    with pytest.raises(ContextCompactionError, match="indivisible"):
        await summarize_bounded(items, settings, session=session, summarize=summarize, allow_image_reduction=True)
    assert not calls
    source = replace(settings, model=settings.model_for_provider("deepseek"))
    record_checkpoint(session, source, "source-prefix")
    summary, usage = await summarize_bounded(items, settings, session=session, summarize=summarize,
                                            allow_image_reduction=True, announce=announcements.append)
    assert calls == ["deepseek-flash"]
    assert "deepseek/deepseek-flash" in announcements[0]
    assert "text description" in summary
    assert usage.total_tokens == 2
    assert await session.get_items() == items


@pytest.mark.asyncio
async def test_summary_chunks_respect_budget_and_call_limit(tmp_path, monkeypatch):
    import deepy.llm.history_migration as migration
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    settings = Settings.from_mapping({"context": {"window_tokens": 60000}})
    items = [{"role": "user", "content": "group " * 3000} for _ in range(8)]
    calls = []
    async def summarize(group, candidate, **kwargs):
        assert estimate_request_value(migration.summary_input(group)) + candidate.model_limits.reserve_tokens < candidate.model_limits.window_tokens
        calls.append(group)
        return "Summary", TokenUsage(prompt_tokens=10, completion_tokens=1, total_tokens=11)
    summary, usage = await summarize_bounded(items, settings, session=session, summarize=summarize)
    assert summary == "Summary"
    assert len(calls) > 1
    assert usage.total_tokens == 11 * len(calls)
    assert migration.MAX_SUMMARY_CALLS == 32
    monkeypatch.setattr(migration, "MAX_SUMMARY_CALLS", 1)
    calls.clear()
    with pytest.raises(ContextCompactionError, match="32-request"):
        await summarize_bounded(items, settings, session=session, summarize=summarize)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_summary_timeout_bound_is_passed_to_wait_for(tmp_path, monkeypatch):
    import deepy.llm.history_migration as migration
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    async def timeout(coro, *, timeout):
        assert timeout == 60
        coro.close()
        raise TimeoutError("injected timeout")
    async def summarize(*args, **kwargs):
        raise AssertionError("not executed")
    monkeypatch.setattr(migration.asyncio, "wait_for", timeout)
    with pytest.raises(ContextCompactionError, match="preserved"):
        await summarize_bounded([{"role": "user", "content": "hi"}], Settings(), session=session, summarize=summarize)


@pytest.mark.asyncio
async def test_failed_final_target_check_does_not_commit_summary(tmp_path, monkeypatch):
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    originals = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "a"}, {"role": "user", "content": "b"}]
    await session.add_items(originals)
    async def summarize(*args, **kwargs):
        return "small", TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", summarize)
    with pytest.raises(ContextCompactionError, match="target budget"):
        await compact_session(session, Settings.from_mapping({"context": {"window_tokens": 60000}}),
                              reason="auto", additional_input="new " * 20000)
    assert await session.get_items() == originals
    assert read_history_state(session)["summary_usage"]["total_tokens"] == 2


def test_foreign_server_ids_are_removed_without_breaking_call_ids():
    target = model_identity("cli_proxy", "gpt-5.6-terra", "http://localhost/v1")
    original = [{"type": "message", "role": "assistant", "id": "foreign-uuid", "content": "answer"},
                {"type": "function_call", "id": "foreign-call", "call_id": "portable", "name": "Read", "arguments": "{}"},
                {"type": "function_call_output", "call_id": "portable", "output": "result"}]
    projected = project_history(original, target)
    assert "id" not in projected[0]
    assert "id" not in projected[1]
    assert projected[1]["call_id"] == projected[2]["call_id"] == "portable"
    assert original[0]["id"] == "foreign-uuid"
    assert len(history_groups(projected)) == 2


def test_summary_uses_its_own_actual_reserve():
    limits = resolve_model_limits("deepseek", "deepseek-flash", reserve_floor=1000)
    budget = request_budget({"input": "hi", "max_output_tokens": 8192}, limits)
    assert budget.reserve_tokens == 8192 + 4096


@pytest.mark.asyncio
async def test_old_schema_migration_is_idempotent_and_keeps_messages(tmp_path):
    import sqlite3
    from deepy.sessions.store_helpers import ensure_schema
    session = DeepySession.create(tmp_path, deepy_home=tmp_path / "home")
    original = [{"role": "user", "content": "legacy"}]
    await session.add_items(original)
    with sqlite3.connect(session.db_path) as conn:
        conn.execute("alter table sessions drop column history_state_json")
        ensure_schema(conn)
        ensure_schema(conn)
        assert conn.execute("select count(*) from session_items").fetchone()[0] == 1
    resumed = DeepySession.open(tmp_path, session.session_id, deepy_home=tmp_path / "home")
    assert await resumed.get_items() == original
    assert read_history_state(resumed) == {}


def test_summary_preserves_tool_arguments_and_pairing():
    from deepy.llm.history_migration import summary_input
    group = tool_items()
    group[0]["arguments"] = '{"path":"important.txt"}'
    prompt = summary_input(group)
    assert "important.txt" in prompt
    assert '"call_id":"a"' in prompt
    assert '"output":"a"' in prompt
