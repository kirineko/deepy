from __future__ import annotations

from deepy.llm.events import normalize_stream_event


def test_normalize_raw_text_delta():
    event = type(
        "Event",
        (),
        {"type": "raw_response_event", "data": type("Data", (), {"delta": "hi"})()},
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "text_delta"
    assert normalized.text == "hi"


def test_normalize_tool_call_event():
    item = type("Item", (), {"tool_name": "read", "call_id": "call-1"})()
    event = type(
        "Event",
        (),
        {"type": "run_item_stream_event", "name": "tool_called", "item": item},
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "tool_call"
    assert normalized.name == "read"
    assert normalized.payload["call_id"] == "call-1"


def test_normalize_tool_output_event():
    item = type("Item", (), {"output": "{\"ok\":true}", "call_id": "call-1"})()
    event = type(
        "Event",
        (),
        {"type": "run_item_stream_event", "name": "tool_output", "item": item},
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "tool_output"
    assert normalized.text == "{\"ok\":true}"


def test_normalize_agent_update_event():
    agent = type("Agent", (), {"name": "Deepy"})()
    event = type("Event", (), {"type": "agent_updated_stream_event", "new_agent": agent})()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "agent_updated"
    assert normalized.name == "Deepy"
