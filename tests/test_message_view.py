from __future__ import annotations

import json

from rich.console import Console

from deepy.ui.message_view import format_tool_output_summary
from deepy.ui.message_view import build_thinking_summary
from deepy.ui.message_view import build_tool_params_snippet
from deepy.ui.message_view import build_tool_result_snippet
from deepy.ui.message_view import DiffPreviewLine
from deepy.ui.message_view import is_invisible_execution
from deepy.ui.message_view import parse_diff_preview
from deepy.ui.message_view import parse_tool_output
from deepy.ui.message_view import render_tool_output
from deepy.ui.message_view import tool_diff_preview
from deepy.ui.message_view import tool_diff_preview_lines


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


def test_tool_diff_preview_prefers_metadata_diff_preview():
    output = json.dumps(
        {
            "ok": True,
            "name": "write",
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": "file",
                "diff": "--- a/file\n+++ b/file\n@@\n-old\n+new\n",
                "diff_preview": " context\n+preview\n",
            },
            "awaitUserResponse": False,
        }
    )

    assert tool_diff_preview(output) == " context\n+preview\n"
    assert tool_diff_preview_lines(output) == [
        DiffPreviewLine(marker=" ", content="context", kind="context"),
        DiffPreviewLine(marker="+", content="preview", kind="added"),
    ]


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


def test_parse_diff_preview_removes_headers_and_classifies_lines():
    lines = parse_diff_preview("--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n context\n-old\n+new")

    assert lines == [
        DiffPreviewLine(marker=" ", content="context", kind="context"),
        DiffPreviewLine(marker="-", content="old", kind="removed"),
        DiffPreviewLine(marker="+", content="new", kind="added"),
    ]


def test_parse_diff_preview_keeps_nonstandard_context_lines():
    assert parse_diff_preview("...\n+added") == [
        DiffPreviewLine(marker=" ", content="...", kind="context"),
        DiffPreviewLine(marker="+", content="added", kind="added"),
    ]


def test_build_thinking_summary_summarizes_content_across_lines():
    assert (
        build_thinking_summary("Plan:\n\nInspect the code   and update tests")
        == "Plan: Inspect the code and update tests"
    )


def test_build_thinking_summary_removes_trailing_colon():
    assert build_thinking_summary("Planning:") == "Planning"
    assert build_thinking_summary("规划：") == "规划"


def test_build_thinking_summary_uses_placeholder_for_hidden_reasoning():
    assert build_thinking_summary("", {"reasoning_content": "hidden chain of thought"}) == (
        "(reasoning...)"
    )


def test_build_tool_params_snippet_formats_bash_command_and_description():
    assert (
        build_tool_params_snippet(
            {"name": "bash", "arguments": '{"command":"pytest","description":"run tests"}'}
        )
        == "pytest  # run tests"
    )


def test_build_tool_params_snippet_shortens_read_path_under_project_root():
    assert (
        build_tool_params_snippet(
            {"name": "read", "arguments": '{"path":"/repo/src/app.py"}'},
            project_root="/repo",
        )
        == "src/app.py"
    )


def test_build_tool_result_snippet_extracts_output_and_truncates():
    content = json.dumps({"ok": True, "name": "bash", "output": "x" * 2_010})

    snippet = build_tool_result_snippet(content)

    assert snippet.startswith("x" * 2_000)
    assert snippet.endswith("... (total 2010 chars)")


def test_is_invisible_execution_detects_failed_bash_payload():
    assert is_invisible_execution(json.dumps({"ok": False, "name": "bash"})) is True
    assert is_invisible_execution(json.dumps({"ok": True, "name": "bash"})) is False
    assert is_invisible_execution(json.dumps({"ok": False, "name": "read"})) is False
