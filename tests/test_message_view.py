from __future__ import annotations

import json

from rich.console import Console

from deepy.ui.message_view import format_tool_output_summary
from deepy.ui.message_view import parse_tool_output
from deepy.ui.message_view import render_tool_output
from deepy.ui.message_view import tool_diff_preview


def test_format_tool_output_summary_uses_path_detail():
    output = (
        '{"ok":true,"name":"read","output":"","error":null,'
        '"metadata":{"path":"/tmp/a"},"awaitUserResponse":false}'
    )

    assert format_tool_output_summary(output) == "read ok - /tmp/a"


def test_format_tool_output_summary_uses_error_detail():
    output = (
        '{"ok":false,"name":"bash","output":"stderr","error":"Command exited with code 1.",'
        '"metadata":{"exitCode":1},"awaitUserResponse":false}'
    )

    assert format_tool_output_summary(output) == "bash failed - Command exited with code 1."


def test_parse_tool_output_preserves_pending_question_state():
    view = parse_tool_output(
        '{"ok":true,"name":"AskUserQuestion","output":"Waiting for user input.","error":null,'
        '"metadata":{"kind":"ask_user_question","questions":[{"question":"Choose one",'
        '"options":[{"label":"Yes"}]}]},"awaitUserResponse":true}'
    )

    assert view.name == "AskUserQuestion"
    assert view.await_user_response is True
    assert view.summary == "AskUserQuestion ok - Waiting for user input."


def test_raw_tool_output_is_truncated():
    summary = format_tool_output_summary("x" * 200)

    assert summary.endswith("... [truncated]")
    assert len(summary) <= 160


def test_tool_diff_preview_only_for_successful_write_or_edit():
    diff = "--- a/file\n+++ b/file\n@@\n-old\n+new\n"
    output = json.dumps(
        {
            "ok": True,
            "name": "edit",
            "output": "Edited file",
            "error": None,
            "metadata": {"path": "file", "diff": diff},
            "awaitUserResponse": False,
        }
    )

    assert tool_diff_preview(output) == diff


def test_tool_diff_preview_ignores_failed_or_unrelated_tools():
    write_failed = (
        '{"ok":false,"name":"write","output":"","error":"denied",'
        '"metadata":{"diff":"--- a\\n+++ b\\n"},"awaitUserResponse":false}'
    )
    read_ok = (
        '{"ok":true,"name":"read","output":"","error":null,'
        '"metadata":{"diff":"--- a\\n+++ b\\n"},"awaitUserResponse":false}'
    )

    assert tool_diff_preview(write_failed) is None
    assert tool_diff_preview(read_ok) is None


def test_render_tool_output_includes_summary_and_diff():
    output = (
        '{"ok":true,"name":"write","output":"Wrote file","error":null,'
        '"metadata":{"path":"file","diff":"--- a/file\\n+++ b/file\\n@@\\n+new\\n"},'
        '"awaitUserResponse":false}'
    )
    console = Console(record=True, width=120)

    console.print(render_tool_output(output))

    rendered = console.export_text()
    assert "write ok - file" in rendered
    assert "+new" in rendered
