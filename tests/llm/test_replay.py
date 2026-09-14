from __future__ import annotations

from types import SimpleNamespace

from deepy.llm.replay import (
    sanitize_sdk_items_for_replay,
    sanitize_model_response_output,
)
from deepy.llm.multimodal import IMAGE_ONLY_DEFAULT_TEXT


def test_sanitize_model_input_drops_empty_assistant_between_tool_call_and_output():
    call = {
        "arguments": '{"file_path":"README.md"}',
        "call_id": "call-read",
        "name": "read_file",
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

    assert sanitize_sdk_items_for_replay([call, empty_message, output]) == [
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
        "name": "read_file",
        "type": "function_call",
    }
    output = {
        "call_id": "call-read",
        "output": '{"ok":true}',
        "type": "function_call_output",
    }

    assert sanitize_sdk_items_for_replay([preamble, call, output]) == [
        preamble,
        call,
        output,
    ]


def test_image_only_input_uses_responses_blocks():
    from deepy.llm.response_images import normalize_response_images
    items = [{"role": "user", "content": [{"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2U="}]}]
    result = normalize_response_images(items)
    assert result[0]["content"][0] == {"type": "input_text", "text": IMAGE_ONLY_DEFAULT_TEXT}
    assert result[0]["content"][1] == items[0]["content"][0]


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
