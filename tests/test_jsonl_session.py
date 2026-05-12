from __future__ import annotations

import json

import pytest

from deepy.sessions import DeepyJsonlSession, list_session_entries, project_code
from deepy.sessions.jsonl import MAX_SESSION_INDEX_ENTRIES, project_sessions_dir


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
    assert records[0]["session_id"] == "s1"
    assert "contentParams" not in records[0]
    assert "messageParams" not in records[0]
    assert "createTime" not in records[0]
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
async def test_session_index_preserves_usage_and_processes_on_touch(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    sessions_dir = project_sessions_dir(project, home)
    sessions_dir.mkdir(parents=True)
    sessions_dir.joinpath("sessions-index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "sessions": [
                    {
                        "id": "s1",
                        "path": "s1.jsonl",
                        "activeTokens": 10,
                        "createdAt": 1,
                        "updatedAt": 2,
                        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
                        "processes": {"123": {"startTime": "now", "command": "pytest"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    session = DeepyJsonlSession.open(project, "s1", deepy_home=home)

    await session.add_items([{"role": "assistant", "content": "hello"}])

    entry = list_session_entries(project, deepy_home=home)[0]
    assert entry.usage == {"prompt_tokens": 12, "completion_tokens": 3}
    assert entry.processes == {"123": {"startTime": "now", "command": "pytest"}}


@pytest.mark.asyncio
async def test_session_record_usage_accumulates_token_usage(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")

    await session.add_items([{"role": "user", "content": "hello"}])
    session.record_usage({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12})
    session.record_usage(
        {
            "prompt_tokens": 3,
            "completion_tokens": 4,
            "total_tokens": 7,
            "completion_tokens_details": {"reasoning_tokens": 2},
        }
    )

    usage = list_session_entries(project, deepy_home=home)[0].usage
    assert usage is not None
    assert usage["prompt_tokens"] == 13
    assert usage["completion_tokens"] == 6
    assert usage["total_tokens"] == 19
    assert usage["reasoning_tokens"] == 2


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


@pytest.mark.asyncio
async def test_session_index_recovers_from_invalid_json_and_trims_entries(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    sessions_dir = project_sessions_dir(project, home)
    sessions_dir.mkdir(parents=True)
    sessions_dir.joinpath("sessions-index.json").write_text("not-json", encoding="utf-8")

    recovered = DeepyJsonlSession.create(project, deepy_home=home, session_id="recovered")
    await recovered.add_items([{"role": "user", "content": "hello"}])

    assert [entry.id for entry in list_session_entries(project, deepy_home=home)] == ["recovered"]

    for index in range(MAX_SESSION_INDEX_ENTRIES + 5):
        session = DeepyJsonlSession.create(project, deepy_home=home, session_id=f"s{index}")
        await session.add_items([{"role": "user", "content": str(index)}])

    entries = list_session_entries(project, deepy_home=home)
    assert len(entries) == MAX_SESSION_INDEX_ENTRIES
    assert entries[0].id == f"s{MAX_SESSION_INDEX_ENTRIES + 4}"
    assert entries[-1].id == "s5"


def test_list_session_entries_ignores_legacy_entries_shape(tmp_path):
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

    assert entries == []


@pytest.mark.asyncio
async def test_jsonl_session_ignores_records_without_sdk_item(tmp_path):
    session = DeepyJsonlSession.create(tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1")
    session.path.parent.mkdir(parents=True)
    records = [
        {
            "id": "user-image",
            "sessionId": "s1",
            "role": "user",
            "content": "look",
            "contentParams": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}}],
            "messageParams": None,
            "compacted": False,
            "visible": True,
        },
        {
            "id": "assistant-tool",
            "sessionId": "s1",
            "role": "assistant",
            "content": "",
            "contentParams": None,
            "messageParams": {
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "read", "arguments": "{}"},
                    }
                ]
            },
            "compacted": False,
            "visible": False,
        },
        {
            "id": "tool-result",
            "sessionId": "s1",
            "role": "tool",
            "content": '{"ok":true}',
            "contentParams": None,
            "messageParams": {"tool_call_id": "call-1"},
            "compacted": False,
            "visible": True,
        },
        {
            "id": "old-summary",
            "sessionId": "s1",
            "role": "system",
            "content": "old compacted summary",
            "contentParams": None,
            "messageParams": None,
            "compacted": True,
            "visible": False,
        },
    ]
    session.path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\nnot-json\n",
        encoding="utf-8",
    )

    assert await session.get_items() == []


@pytest.mark.asyncio
async def test_jsonl_session_does_not_repair_legacy_missing_tool_pairs(tmp_path):
    session = DeepyJsonlSession.create(tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1")
    session.path.parent.mkdir(parents=True)
    records = [
        {
            "id": "assistant-tool",
            "sessionId": "s1",
            "role": "assistant",
            "content": "I will run a tool.",
            "contentParams": None,
            "messageParams": {
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "bash", "arguments": '{"command":"sleep 100"}'},
                    }
                ]
            },
            "compacted": False,
            "visible": True,
        },
        {
            "id": "user-after",
            "sessionId": "s1",
            "role": "user",
            "content": "continue",
            "contentParams": None,
            "messageParams": None,
            "compacted": False,
            "visible": True,
        },
    ]
    session.path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    assert await session.get_items() == []


@pytest.mark.asyncio
async def test_jsonl_session_round_trips_sdk_tool_items(tmp_path):
    session = DeepyJsonlSession.create(tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1")

    sdk_items = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "bash", "arguments": '{"command":"date"}'},
                }
            ],
        },
        {
            "role": "tool",
            "content": json.dumps({"ok": True, "name": "bash", "output": "real result"}),
            "tool_call_id": "call-1",
        },
    ]

    await session.add_items(sdk_items)

    assert await session.get_items() == sdk_items
