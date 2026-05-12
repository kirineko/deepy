from __future__ import annotations

from types import SimpleNamespace

from deepy.llm.events import normalize_stream_event


def test_normalize_raw_text_delta():
    event = type(
        "Event",
        (),
        {
            "type": "raw_response_event",
            "data": type("Data", (), {"type": "response.output_text.delta", "delta": "hi"})(),
        },
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "text_delta"
    assert normalized.text == "hi"


def test_normalize_tool_argument_delta_does_not_emit_text():
    event = type(
        "Event",
        (),
        {
            "type": "raw_response_event",
            "data": type(
                "Data",
                (),
                {
                    "type": "response.function_call_arguments.delta",
                    "delta": '{"file_path": "README.md"}',
                },
            )(),
        },
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "raw_response"
    assert normalized.text == '{"file_path": "README.md"}'


def test_normalize_reasoning_delta():
    event = type(
        "Event",
        (),
        {
            "type": "raw_response_event",
            "data": type(
                "Data",
                (),
                {"type": "response.reasoning_summary_text.delta", "delta": "thinking"},
            )(),
        },
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "reasoning_delta"
    assert normalized.text == "thinking"


def test_normalize_reasoning_text_delta():
    event = type(
        "Event",
        (),
        {
            "type": "raw_response_event",
            "data": type(
                "Data",
                (),
                {"type": "response.reasoning_text.delta", "delta": "思考"},
            )(),
        },
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "reasoning_delta"
    assert normalized.text == "思考"


def test_normalize_response_completed_usage():
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)
    response = SimpleNamespace(usage=usage)
    event = type(
        "Event",
        (),
        {
            "type": "raw_response_event",
            "data": type("Data", (), {"type": "response.completed", "response": response})(),
        },
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "usage"
    assert normalized.payload["usage"] == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }


def test_normalize_raw_response_without_special_handling():
    data = type("Data", (), {"type": "response.created"})()
    event = type("Event", (), {"type": "raw_response_event", "data": data})()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "raw_response"
    assert normalized.name == "response.created"


def test_normalize_tool_call_event():
    item = type(
        "Item",
        (),
        {"tool_name": "read", "call_id": "call-1", "arguments": '{"file_path":"README.md"}'},
    )()
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
    assert normalized.payload["arguments"] == '{"file_path":"README.md"}'


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


def test_normalize_reasoning_item_event():
    item = type("ReasoningItem", (), {"raw_item": {"type": "reasoning"}})()
    event = type(
        "Event",
        (),
        {"type": "run_item_stream_event", "name": "reasoning_item_created", "item": item},
    )()

    normalized = normalize_stream_event(event)

    assert normalized is not None
    assert normalized.kind == "reasoning_item"
    assert normalized.payload["item"] is item
