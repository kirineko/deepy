from __future__ import annotations

import json

import pytest

from deepy.llm.runner import RunSummary
from deepy.sessions import list_session_entries
from deepy.sessions.jsonl import project_sessions_dir
from deepy.sessions.manager import DeepySessionManager


@pytest.mark.asyncio
async def test_session_manager_creates_and_replies_to_active_session(monkeypatch, tmp_path):
    calls: list[dict] = []

    async def fake_run_prompt_once(prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return RunSummary(output="ok", session_id=kwargs.get("session_id") or "created", complete=True)

    monkeypatch.setattr("deepy.sessions.manager.run_prompt_once", fake_run_prompt_once)
    manager = DeepySessionManager(project_root=tmp_path)

    created = await manager.handle_user_prompt("hello", max_turns=2)
    replied = await manager.handle_user_prompt("again", max_turns=3)

    assert created.session_id == "created"
    assert replied.session_id == "created"
    assert manager.active_session_id == "created"
    assert calls[0]["session_id"] is None
    assert calls[0]["max_turns"] == 2
    assert calls[1]["session_id"] == "created"
    assert calls[1]["max_turns"] == 3


@pytest.mark.asyncio
async def test_session_manager_append_and_compact_session(monkeypatch, tmp_path):
    async def fake_run_compaction_model(items, settings, *, provider=None, focus_instruction=None):
        assert [item["content"] for item in items] == ["one"]
        assert focus_instruction == "keep decisions"
        from deepy.usage import TokenUsage

        return "Summary of one.", TokenUsage(completion_tokens=4, total_tokens=4)

    monkeypatch.setattr("deepy.llm.compaction.run_compaction_model", fake_run_compaction_model)
    manager = DeepySessionManager(project_root=tmp_path, deepy_home=tmp_path / "home")

    await manager.append_sdk_items(
        "s1",
        [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
        ],
    )
    assert list_session_entries(tmp_path, deepy_home=tmp_path / "home")[0].id == "s1"

    result = await manager.compact_session("s1", focus_instruction="keep decisions")

    from deepy.sessions import DeepyJsonlSession

    items = await DeepyJsonlSession.open(tmp_path, "s1", deepy_home=tmp_path / "home").get_items()
    assert result.compacted is True
    assert result.archive_path is not None
    assert result.archive_path.exists()
    assert "Previous context has been compacted" in items[0]["content"]
    assert items[1:] == [
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]


@pytest.mark.asyncio
async def test_session_manager_compact_keeps_short_session_unchanged(tmp_path):
    manager = DeepySessionManager(project_root=tmp_path, deepy_home=tmp_path / "home")

    await manager.append_sdk_items("s1", [{"role": "user", "content": "hello"}])
    result = await manager.compact_session("s1")

    assert result.compacted is False
    from deepy.sessions import DeepyJsonlSession

    items = await DeepyJsonlSession.open(tmp_path, "s1", deepy_home=tmp_path / "home").get_items()
    assert items == [{"role": "user", "content": "hello"}]


def test_session_manager_interrupts_active_session_and_clears_processes(monkeypatch, tmp_path):
    home = tmp_path / "home"
    sessions_dir = project_sessions_dir(tmp_path, home)
    sessions_dir.mkdir(parents=True)
    sessions_dir.joinpath("sessions-index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "sessions": [
                    {
                        "id": "s1",
                        "path": "s1.jsonl",
                        "activeTokens": 0,
                        "createdAt": 1,
                        "updatedAt": 2,
                        "processes": {"123": {"startTime": "now", "command": "pytest"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    killed_groups: list[int] = []

    def fake_killpg(pid, sig):
        killed_groups.append(pid)

    monkeypatch.setattr("deepy.sessions.manager.os.killpg", fake_killpg)
    manager = DeepySessionManager(project_root=tmp_path, deepy_home=home)
    manager.activate_session("s1")

    summary = manager.interrupt_active_session()

    assert summary is not None
    assert summary.session_id == "s1"
    assert summary.killed_pids == [123]
    assert killed_groups == [123]
    assert list_session_entries(tmp_path, deepy_home=home)[0].processes is None


@pytest.mark.asyncio
async def test_session_manager_passes_interrupt_check_to_runner(monkeypatch, tmp_path):
    observed_interrupt: list[bool] = []

    async def fake_run_prompt_once(prompt, **kwargs):
        observed_interrupt.append(kwargs["should_interrupt"]())
        return RunSummary(output="", session_id=kwargs["session_id"], complete=False, interrupted=True)

    monkeypatch.setattr("deepy.sessions.manager.run_prompt_once", fake_run_prompt_once)
    manager = DeepySessionManager(project_root=tmp_path)
    manager.activate_session("s1")
    manager.interrupt_session("s1")

    summary = await manager.reply_session("s1", "continue")

    assert summary.interrupted is True
    assert observed_interrupt == [True]
