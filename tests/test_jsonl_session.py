from __future__ import annotations

import json

import pytest

from deepy.sessions import DeepyJsonlSession, list_session_entries, project_code
from deepy.sessions.jsonl import project_sessions_dir


def test_project_code_matches_deepcode_shape(tmp_path):
    assert project_code(tmp_path).startswith("-")
    assert "/" not in project_code(tmp_path)


@pytest.mark.asyncio
async def test_jsonl_session_round_trips_sdk_items(tmp_path):
    session = DeepyJsonlSession.create(tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1")

    await session.add_items([{"role": "user", "content": "hello"}])
    await session.add_items([{"role": "assistant", "content": "hi"}])

    assert await session.get_items() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    assert await session.get_items(limit=1) == [{"role": "assistant", "content": "hi"}]
    assert await session.get_items(limit=0) == []

    records = [
        json.loads(line)
        for line in session.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records[0]["sessionId"] == "s1"
    assert records[0]["meta"]["sdk_item"] == {"role": "user", "content": "hello"}

    popped = await session.pop_item()
    assert popped == {"role": "assistant", "content": "hi"}
    assert await session.get_items() == [{"role": "user", "content": "hello"}]

    await session.clear_session()
    assert await session.get_items() == []


@pytest.mark.asyncio
async def test_session_index_preserves_created_at_and_lists_sessions(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")

    await session.add_items([{"role": "user", "content": "one"}])
    first_entry = list_session_entries(project, deepy_home=home)[0]
    await session.add_items([{"role": "assistant", "content": "two"}])
    second_entry = list_session_entries(project, deepy_home=home)[0]

    assert first_entry.id == "s1"
    assert first_entry.active_tokens > 0
    assert second_entry.created_at == first_entry.created_at
    assert second_entry.updated_at >= first_entry.updated_at
    assert second_entry.active_tokens >= first_entry.active_tokens


@pytest.mark.asyncio
async def test_open_existing_session_reads_same_jsonl(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    created = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")
    await created.add_items([{"role": "user", "content": "hello"}])

    opened = DeepyJsonlSession.open(project, "s1", deepy_home=home)

    assert await opened.get_items() == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_clear_session_resets_active_tokens(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")
    await session.add_items([{"role": "user", "content": "hello world"}])

    await session.clear_session()

    assert list_session_entries(project, deepy_home=home)[0].active_tokens == 0


def test_list_session_entries_reads_legacy_entries_shape(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    sessions_dir = project_sessions_dir(project, home)
    sessions_dir.mkdir(parents=True)
    sessions_dir.joinpath("sessions-index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "originalPath": str(project),
                "entries": [
                    {
                        "id": "legacy-session",
                        "status": "completed",
                        "createTime": "2026-01-01T00:00:00.000Z",
                        "updateTime": "2026-01-01T00:00:01.000Z",
                        "processes": {
                            "123": "2026-01-01T00:00:00.000Z",
                            "456": {
                                "startTime": "2026-01-01T00:00:00.000Z",
                                "command": "pytest",
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    entries = list_session_entries(project, deepy_home=home)

    assert len(entries) == 1
    assert entries[0].id == "legacy-session"
    assert entries[0].path == "legacy-session.jsonl"
    assert entries[0].active_tokens == 0
    assert entries[0].created_at == 1767225600000
    assert entries[0].updated_at == 1767225601000
    assert entries[0].processes == {
        "123": {
            "startTime": "2026-01-01T00:00:00.000Z",
            "command": "Running process...",
        },
        "456": {
            "startTime": "2026-01-01T00:00:00.000Z",
            "command": "pytest",
        },
    }
