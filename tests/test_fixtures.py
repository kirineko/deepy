from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from deepy.sessions import DeepyJsonlSession, list_session_entries
from deepy.sessions.jsonl import project_sessions_dir


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_session_jsonl_fixture_replays_legacy_shapes(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    deepy_home = tmp_path / "home"
    sessions_dir = project_sessions_dir(project_root, deepy_home)
    sessions_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "sessions" / "sessions-index.json", sessions_dir / "sessions-index.json")
    shutil.copy(
        FIXTURES / "sessions" / "fixture-session.jsonl",
        sessions_dir / "fixture-session.jsonl",
    )

    entries = list_session_entries(project_root, deepy_home=deepy_home)
    session = DeepyJsonlSession.open(project_root, "fixture-session", deepy_home=deepy_home)
    items = await session.get_items()

    assert entries[0].processes == {
        "4242": {"command": "pytest", "startTime": "2026-05-11T00:00:00.000Z"}
    }
    assert [item["role"] for item in items] == [
        "user",
        "assistant",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert items[2]["tool_calls"][0]["id"] == "call-read"
    assert items[3]["tool_call_id"] == "call-read"
    assert items[4]["reasoning_content"] == "Checked the file before answering."
    assert isinstance(items[5]["content"], list)


def test_tool_fixture_covers_planned_cases():
    payload = json.loads((FIXTURES / "tools" / "tool_cases.json").read_text(encoding="utf-8"))
    names = {item["name"] for item in payload["cases"]}

    assert names == {
        "read_full_text",
        "read_partial_text_with_snippet",
        "edit_by_snippet",
        "write_existing_without_read_rejected",
        "edit_stale_read_rejected",
        "replace_all_guard",
        "bash_cwd_persistence",
    }
