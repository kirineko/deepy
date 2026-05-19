from __future__ import annotations

import json

import pytest

from deepy.sessions import DeepyJsonlSession, list_session_entries, project_code
from deepy.llm.context import estimate_tokens_for_item
from deepy.sessions.jsonl import MAX_SESSION_INDEX_ENTRIES, project_sessions_dir


def test_project_code_matches_deepcode_shape(tmp_path):
    assert project_code(tmp_path).startswith("-")
    assert "/" not in project_code(tmp_path)


@pytest.mark.asyncio
async def test_jsonl_session_round_trips_sdk_items(tmp_path):
    session = DeepyJsonlSession.create(
        tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1"
    )

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
    assert session.latest_context_window_usage() is None


@pytest.mark.asyncio
async def test_session_index_persists_latest_todo_state_from_tool_output(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")
    todo_output = json.dumps(
        {
            "ok": True,
            "name": "todo_write",
            "output": "Todo list updated",
            "metadata": {
                "kind": "todo_list",
                "todos": [
                    {"id": "one", "content": "Inspect code", "status": "completed"},
                    {"id": "two", "content": "Implement", "status": "in_progress"},
                ],
            },
            "awaitUserResponse": False,
        }
    )

    await session.add_items(
        [
            {
                "type": "function_call",
                "call_id": "call-todo",
                "name": "todo_write",
                "arguments": "{}",
            },
            {"type": "function_call_output", "call_id": "call-todo", "output": todo_output},
        ]
    )

    expected = [
        {"id": "one", "content": "Inspect code", "status": "completed"},
        {"id": "two", "content": "Implement", "status": "in_progress"},
    ]
    assert session.todo_state() == expected
    assert list_session_entries(project, deepy_home=home)[0].todo_state == expected


@pytest.mark.asyncio
async def test_session_index_preserves_previous_todo_state_on_invalid_update(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")
    valid_output = json.dumps(
        {
            "ok": True,
            "name": "todo_write",
            "output": "Todo list updated",
            "metadata": {
                "kind": "todo_list",
                "todos": [{"id": "one", "content": "One", "status": "in_progress"}],
            },
            "awaitUserResponse": False,
        }
    )
    invalid_output = json.dumps(
        {
            "ok": False,
            "name": "todo_write",
            "output": "",
            "error": "only one todo item may be in_progress.",
            "metadata": {"kind": "todo_list_error"},
            "awaitUserResponse": False,
        }
    )

    await session.add_items(
        [{"type": "function_call_output", "call_id": "valid", "output": valid_output}]
    )
    await session.add_items(
        [{"type": "function_call_output", "call_id": "invalid", "output": invalid_output}]
    )

    assert session.todo_state() == [{"id": "one", "content": "One", "status": "in_progress"}]


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
    entry = list_session_entries(project, deepy_home=home)[0]
    assert entry.latest_context_window_tokens == 7
    latest_usage = session.latest_context_window_usage()
    assert latest_usage is not None
    assert latest_usage.used_tokens == 7


@pytest.mark.asyncio
async def test_session_records_input_suggestion_usage_separately(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")

    await session.add_items([{"role": "user", "content": "hello"}])
    session.record_usage({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12})
    before_context_usage = session.latest_context_window_usage()
    session.record_input_suggestion_usage(
        {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        model="deepseek-v4-flash",
        elapsed_ms=25,
    )

    entry = list_session_entries(project, deepy_home=home)[0]
    assert entry.usage is not None
    assert entry.usage["total_tokens"] == 12
    assert entry.input_suggestion_usage is not None
    assert entry.input_suggestion_usage["total_tokens"] == 4
    assert entry.input_suggestion_usage["model"] == "deepseek-v4-flash"
    assert entry.input_suggestion_usage["elapsed_ms"] == 25
    assert session.latest_context_window_usage() == before_context_usage


@pytest.mark.asyncio
async def test_session_token_state_tracks_usage_checkpoint_and_pending(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")

    await session.add_items([{"role": "user", "content": "hello"}])
    session.record_usage({"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105})
    await session.add_items([{"role": "assistant", "content": "x" * 400}])

    state = session.context_token_state()
    entry = list_session_entries(project, deepy_home=home)[0]

    assert state.last_usage_tokens == 100
    assert state.pending_tokens > 0
    assert state.active_tokens == 100 + state.pending_tokens
    assert entry.last_usage_tokens == 100
    assert entry.pending_tokens == state.pending_tokens
    assert entry.active_tokens == state.active_tokens


@pytest.mark.asyncio
async def test_session_token_state_does_not_shrink_on_short_latest_usage(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")

    await session.add_items([{"role": "user", "content": "large prompt"}])
    session.record_usage({"prompt_tokens": 9_000, "completion_tokens": 100, "total_tokens": 9_100})
    await session.add_items(
        [
            {"role": "assistant", "content": "large answer"},
            {"role": "user", "content": "hi"},
        ]
    )
    before_short_usage = session.context_token_state()

    session.record_usage({"prompt_tokens": 3_500, "completion_tokens": 10, "total_tokens": 3_510})

    state = session.context_token_state()
    entry = list_session_entries(project, deepy_home=home)[0]

    assert before_short_usage.active_tokens > 9_000
    assert state.active_tokens == before_short_usage.active_tokens
    assert state.last_usage_tokens == before_short_usage.active_tokens
    assert state.pending_tokens == 0
    assert entry.active_tokens == state.active_tokens
    assert entry.usage is not None
    assert entry.usage["prompt_tokens"] == 12_500
    assert entry.usage["total_tokens"] == 12_610


@pytest.mark.asyncio
async def test_context_token_state_falls_back_when_checkpoint_is_undercounted(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")
    items = [
        {"role": "user", "content": "x" * 1_000},
        {"role": "assistant", "content": "y" * 1_000},
    ]
    await session.add_items(items)
    session._touch_index(
        active_tokens=10,
        last_usage_tokens=10,
        pending_tokens=0,
        last_usage_record_count=2,
    )

    state = session.context_token_state()

    assert state.active_tokens >= sum(estimate_tokens_for_item(item) for item in items)
    assert state.active_tokens > 10


@pytest.mark.asyncio
async def test_replace_items_resets_checkpoint_to_compacted_estimate(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")

    await session.add_items([{"role": "user", "content": "hello"}])
    await session.replace_items(
        [{"role": "user", "content": "Previous context has been compacted."}],
        active_tokens=12,
    )

    state = session.context_token_state()
    entry = list_session_entries(project, deepy_home=home)[0]

    assert state.active_tokens == 12
    assert state.last_usage_tokens == 12
    assert state.pending_tokens == 0
    assert state.last_usage_record_count == 1
    assert entry.active_tokens == 12
    assert entry.latest_context_window_tokens == 12
    assert entry.pending_tokens == 0
    latest_usage = session.latest_context_window_usage()
    assert latest_usage is not None
    assert latest_usage.used_tokens == 12


@pytest.mark.asyncio
async def test_replace_items_preserves_todo_state(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")
    todo_output = json.dumps(
        {
            "ok": True,
            "name": "todo_write",
            "output": "Todo list updated",
            "metadata": {
                "kind": "todo_list",
                "todos": [{"id": "one", "content": "One", "status": "in_progress"}],
            },
            "awaitUserResponse": False,
        }
    )
    await session.add_items(
        [{"type": "function_call_output", "call_id": "todo", "output": todo_output}]
    )

    await session.replace_items([{"role": "user", "content": "summary"}], active_tokens=10)

    assert session.todo_state() == [{"id": "one", "content": "One", "status": "in_progress"}]


@pytest.mark.asyncio
async def test_context_token_state_reestimates_when_history_is_shortened(tmp_path):
    project = tmp_path / "project"
    home = tmp_path / "home"
    session = DeepyJsonlSession.create(project, deepy_home=home, session_id="s1")

    await session.add_items(
        [
            {"role": "user", "content": "large prompt"},
            {"role": "assistant", "content": "large answer"},
        ]
    )
    session.record_usage({"prompt_tokens": 9_000, "completion_tokens": 10, "total_tokens": 9_010})

    await session.pop_item()

    state = session.context_token_state()
    entry = list_session_entries(project, deepy_home=home)[0]
    assert state.active_tokens < 9_000
    assert state.last_usage_tokens is None
    assert state.last_usage_record_count is None
    assert entry.latest_context_window_tokens == state.active_tokens


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

    entry = list_session_entries(project, deepy_home=home)[0]
    assert entry.active_tokens == 0
    assert entry.latest_context_window_tokens == 0
    latest_usage = session.latest_context_window_usage()
    assert latest_usage is not None
    assert latest_usage.used_tokens == 0
    assert entry.todo_state == []


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
    session = DeepyJsonlSession.create(
        tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1"
    )
    session.path.parent.mkdir(parents=True)
    records = [
        {
            "id": "user-image",
            "sessionId": "s1",
            "role": "user",
            "content": "look",
            "contentParams": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}}
            ],
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
    session = DeepyJsonlSession.create(
        tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1"
    )
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
                        "function": {"name": "shell", "arguments": '{"command":"sleep 100"}'},
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
    session.path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )

    assert await session.get_items() == []


@pytest.mark.asyncio
async def test_jsonl_session_round_trips_sdk_tool_items(tmp_path):
    session = DeepyJsonlSession.create(
        tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1"
    )

    sdk_items = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "shell", "arguments": '{"command":"date"}'},
                }
            ],
        },
        {
            "role": "tool",
            "content": json.dumps({"ok": True, "name": "shell", "output": "real result"}),
            "tool_call_id": "call-1",
        },
    ]

    await session.add_items(sdk_items)

    assert await session.get_items() == sdk_items


@pytest.mark.asyncio
async def test_jsonl_session_drops_empty_assistant_between_function_calls_and_outputs(tmp_path):
    session = DeepyJsonlSession.create(
        tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1"
    )

    sdk_items = [
        {
            "arguments": '{"file_path":"README.md"}',
            "call_id": "call-read",
            "name": "read",
            "type": "function_call",
        },
        {
            "id": "__fake_id__",
            "content": [{"annotations": [], "text": "", "type": "output_text"}],
            "role": "assistant",
            "status": "completed",
            "type": "message",
        },
        {
            "call_id": "call-read",
            "output": json.dumps({"ok": True, "name": "read", "output": "README"}),
            "type": "function_call_output",
        },
    ]

    await session.add_items(sdk_items)

    assert await DeepyJsonlSession.open(
        tmp_path / "project",
        "s1",
        deepy_home=tmp_path / "home",
    ).get_items() == [sdk_items[0], sdk_items[2]]


@pytest.mark.asyncio
async def test_jsonl_session_sanitizes_loaded_cache_after_append(tmp_path):
    session = DeepyJsonlSession.create(
        tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1"
    )
    first_item = {"role": "user", "content": "hello"}
    await session.add_items([first_item])
    assert await session.get_items() == [first_item]

    sdk_items = [
        {
            "arguments": '{"file_path":"README.md"}',
            "call_id": "call-read",
            "name": "read",
            "type": "function_call",
        },
        {
            "id": "__fake_id__",
            "content": [{"annotations": [], "text": "", "type": "output_text"}],
            "role": "assistant",
            "status": "completed",
            "type": "message",
        },
        {
            "call_id": "call-read",
            "output": json.dumps({"ok": True, "name": "read", "output": "README"}),
            "type": "function_call_output",
        },
    ]

    await session.add_items(sdk_items)

    assert await session.get_items() == [first_item, sdk_items[0], sdk_items[2]]
