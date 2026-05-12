from __future__ import annotations

from types import SimpleNamespace

from deepy.llm.replay import (
    sanitize_chat_completion_stream_event,
    sanitize_model_input_for_chat_completions,
    sanitize_model_response_output,
)


def test_sanitize_model_input_drops_empty_assistant_between_tool_call_and_output():
    call = {
        "arguments": '{"file_path":"README.md"}',
        "call_id": "call-read",
        "name": "read",
        "type": "function_call",
    }
    empty_message = {
        "id": "__fake_id__",
        "content": [{"annotations": [], "text": "", "type": "output_text"}],
        "role": "assistant",
        "status": "completed",
        "type": "message",
    }
    output = {
        "call_id": "call-read",
        "output": '{"ok":true}',
        "type": "function_call_output",
    }

    assert sanitize_model_input_for_chat_completions([call, empty_message, output]) == [
        call,
        output,
    ]


def test_sanitize_model_input_keeps_non_empty_assistant_preamble():
    preamble = {
        "id": "__fake_id__",
        "content": [{"annotations": [], "text": "I will inspect the project.", "type": "output_text"}],
        "role": "assistant",
        "status": "completed",
        "type": "message",
    }
    call = {
        "arguments": '{"file_path":"README.md"}',
        "call_id": "call-read",
        "name": "read",
        "type": "function_call",
    }
    output = {
        "call_id": "call-read",
        "output": '{"ok":true}',
        "type": "function_call_output",
    }

    assert sanitize_model_input_for_chat_completions([preamble, call, output]) == [
        preamble,
        call,
        output,
    ]


def test_sanitize_model_response_output_drops_empty_assistant_message():
    call = SimpleNamespace(type="function_call", call_id="call-read")
    empty_message = SimpleNamespace(
        type="message",
        role="assistant",
        content=[SimpleNamespace(type="output_text", text="")],
    )
    preamble = SimpleNamespace(
        type="message",
        role="assistant",
        content=[SimpleNamespace(type="output_text", text="Reading project files.")],
    )

    assert sanitize_model_response_output([call, empty_message, preamble]) == [call, preamble]


def test_sanitize_stream_event_suppresses_empty_assistant_done_event():
    event = SimpleNamespace(
        type="response.output_item.done",
        item=SimpleNamespace(
            type="message",
            role="assistant",
            content=[SimpleNamespace(type="output_text", text="")],
        ),
    )

    assert sanitize_chat_completion_stream_event(event) is None


def test_sanitize_stream_event_cleans_completed_response_output():
    call = SimpleNamespace(type="function_call", call_id="call-read")
    empty_message = SimpleNamespace(
        type="message",
        role="assistant",
        content=[SimpleNamespace(type="output_text", text="")],
    )
    event = SimpleNamespace(
        type="response.completed",
        response=SimpleNamespace(output=[call, empty_message]),
    )

    assert sanitize_chat_completion_stream_event(event) is event
    assert event.response.output == [call]
