from __future__ import annotations

import json

import pytest

from deepy.sessions import DeepyJsonlSession, project_code


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
