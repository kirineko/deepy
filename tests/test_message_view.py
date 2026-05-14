from __future__ import annotations

import json

from rich.console import Console

from deepy.ui.message_view import format_tool_output_summary
from deepy.ui.message_view import format_tool_progress_summary
from deepy.ui.message_view import format_tool_call_summary
from deepy.ui.message_view import build_thinking_summary
from deepy.ui.message_view import build_tool_params_snippet
from deepy.ui.message_view import build_tool_result_snippet
from deepy.ui.message_view import DiffPreviewLine
from deepy.ui.message_view import is_invisible_execution
from deepy.ui.message_view import parse_diff_preview
from deepy.ui.message_view import parse_tool_output
from deepy.ui.message_view import render_diff_preview_line
from deepy.ui.message_view import render_message
from deepy.ui.message_view import render_tool_diff_preview
from deepy.ui.message_view import render_tool_output
from deepy.ui.message_view import tool_diff_preview
from deepy.ui.message_view import tool_diff_preview_lines
from deepy.ui.styles import LIGHT_PALETTE


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


def test_tool_diff_preview_only_for_successful_edit():
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


def test_tool_diff_preview_prefers_write_metadata_diff_preview():
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
        '{"ok":true,"name":"edit","output":"Edited file","error":null,'
        '"metadata":{"path":"file","diff":"--- a/file\\n+++ b/file\\n@@\\n+new\\n"},'
        '"awaitUserResponse":false}'
    )
    console = Console(record=True, width=120)

    console.print(render_tool_output(output))

    rendered = console.export_text()
    assert "edit ok - file" in rendered
    assert "Edited file (+1 -0)" in rendered
    assert "new" in rendered
    assert "+new" not in rendered


def test_render_tool_output_shows_write_preview_without_background():
    output = (
        '{"ok":true,"name":"write","output":"Wrote file","error":null,'
        '"metadata":{"path":"file","diff":"--- /dev/null\\n+++ b/file\\n@@ -0,0 +1,1 @@\\n+new\\n"},'
        '"awaitUserResponse":false}'
    )
    console = Console(record=True, width=120)

    console.print(render_tool_output(output))

    rendered = console.export_text()
    assert "write ok - file" in rendered
    assert "Wrote file (+1 -0)" in rendered
    assert "new" in rendered
    assert "+new" not in rendered


def test_render_tool_diff_preview_hides_headers_and_markers():
    output = json.dumps(
        {
            "ok": True,
            "name": "edit",
            "output": "Edited file",
            "error": None,
            "metadata": {
                "path": "file",
                "diff": "--- a/file\n+++ b/file\n@@ -1,2 +1,2 @@\n-old\n+new\n same\n",
            },
            "awaitUserResponse": False,
        }
    )
    console = Console(record=True, width=120)

    console.print(render_tool_diff_preview(output))

    rendered = console.export_text()
    assert "Edited file (+1 -1)" in rendered
    assert "old" in rendered
    assert "new" in rendered
    assert "same" in rendered
    assert "---" not in rendered
    assert "+++" not in rendered
    assert "@@" not in rendered
    assert "-old" not in rendered
    assert "+new" not in rendered


def test_render_diff_preview_line_uses_background_for_changes():
    removed = render_diff_preview_line(
        DiffPreviewLine(marker="-", content="old", kind="removed", old_lineno=12)
    )
    added = render_diff_preview_line(
        DiffPreviewLine(marker="+", content="new", kind="added", new_lineno=13)
    )

    assert removed.plain == "  12      - old"
    assert added.plain == "       13 + new"
    assert "#7f1d1d" in str(removed.spans)
    assert "#14532d" in str(added.spans)


def test_render_diff_preview_line_uses_light_theme_contrast():
    removed = render_diff_preview_line(
        DiffPreviewLine(marker="-", content="old", kind="removed", old_lineno=12),
        palette=LIGHT_PALETTE,
    )
    added = render_diff_preview_line(
        DiffPreviewLine(marker="+", content="new", kind="added", new_lineno=13),
        palette=LIGHT_PALETTE,
    )

    assert "#fee2e2" in str(removed.spans)
    assert "#dcfce7" in str(added.spans)


def test_render_write_preview_line_has_no_background_for_content():
    output = json.dumps(
        {
            "ok": True,
            "name": "write",
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": "file",
                "diff": "--- /dev/null\n+++ b/file\n@@ -0,0 +1,1 @@\n+let x = 1;\n",
            },
            "awaitUserResponse": False,
        }
    )
    rendered = render_tool_diff_preview(output)
    assert rendered is not None
    lines = list(rendered.renderables)

    assert "Wrote file (+1 -0)" in lines[0].plain
    assert lines[1].plain == "   1   let x = 1;"
    assert "#1f2937" in str(lines[1].spans)


def test_render_write_preview_line_uses_light_theme_background():
    output = json.dumps(
        {
            "ok": True,
            "name": "write",
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": "file",
                "diff": "--- /dev/null\n+++ b/file\n@@ -0,0 +1,1 @@\n+let x = 1;\n",
            },
            "awaitUserResponse": False,
        }
    )
    rendered = render_tool_diff_preview(output, palette=LIGHT_PALETTE)
    assert rendered is not None
    lines = list(rendered.renderables)

    assert "#f8fafc" in str(lines[1].spans)


def test_render_write_preview_does_not_truncate_large_writes():
    body = "\n".join(f"+line {index}" for index in range(1, 91))
    output = json.dumps(
        {
            "ok": True,
            "name": "write",
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": "file",
                "diff": f"--- /dev/null\n+++ b/file\n@@ -0,0 +90,90 @@\n{body}\n",
            },
            "awaitUserResponse": False,
        }
    )
    console = Console(record=True, width=120)

    console.print(render_tool_diff_preview(output))

    rendered = console.export_text()
    assert "line 1" in rendered
    assert "line 90" in rendered
    assert "truncated" not in rendered


def test_render_message_renders_user_and_assistant_panels():
    console = Console(record=True, width=120)

    console.print(render_message({"role": "user", "content": "hello"}))
    console.print(render_message({"role": "assistant", "content": "hi"}))

    rendered = console.export_text()
    assert "You" in rendered
    assert "hello" in rendered
    assert "Deepy" in rendered
    assert "hi" in rendered


def test_render_message_renders_system_skill_and_summary_labels():
    console = Console(record=True, width=120)

    console.print(render_message({"role": "system", "content": "Loaded skills:\nreview"}))
    console.print(render_message({"role": "system", "content": "Earlier conversation was compacted."}))

    rendered = console.export_text()
    assert "System Skill" in rendered
    assert "Summary" in rendered


def test_render_message_renders_tool_outputs():
    console = Console(record=True, width=120)

    console.print(
        render_message(
            {
                "role": "tool",
                "content": '{"ok":true,"name":"read","output":"","metadata":{"path":"file"}}',
            }
        )
    )

    assert "read ok - file" in console.export_text()


def test_parse_diff_preview_removes_headers_and_classifies_lines():
    lines = parse_diff_preview("--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n context\n-old\n+new")

    assert lines == [
        DiffPreviewLine(marker=" ", content="context", kind="context", old_lineno=1, new_lineno=1),
        DiffPreviewLine(marker="-", content="old", kind="removed", old_lineno=2),
        DiffPreviewLine(marker="+", content="new", kind="added", new_lineno=2),
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


def test_build_thinking_summary_keeps_moderate_content_untruncated():
    content = " ".join(["step"] * 60)

    assert "[truncated]" not in build_thinking_summary(content)


def test_build_thinking_summary_truncates_very_long_content():
    content = " ".join(["step"] * 120)

    assert "[truncated]" in build_thinking_summary(content)


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


def test_format_tool_call_summary_formats_read_arguments():
    assert (
        format_tool_call_summary(
            "read",
            '{"file_path":"/repo/README.md"}',
            project_root="/repo",
        )
        == "read README.md"
    )


def test_format_tool_call_summary_formats_write_without_content_body():
    summary = format_tool_call_summary(
        "write",
        json.dumps(
            {
                "file_path": "/repo/src/lib.rs",
                "content": "fn main() {\n    println!(\"hi\");\n}\n",
            }
        ),
        project_root="/repo",
    )

    assert summary == "write src/lib.rs (4 lines, 34 chars)"
    assert "println" not in summary


def test_format_tool_call_summary_formats_modify_create_without_content_body():
    summary = format_tool_call_summary(
        "modify",
        json.dumps(
            {
                "file_path": "/repo/src/lib.rs",
                "content": "fn main() {\n    println!(\"hi\");\n}\n",
            }
        ),
        project_root="/repo",
    )

    assert summary == "modify src/lib.rs (4 lines, 34 chars)"
    assert "println" not in summary


def test_format_tool_progress_summary_merges_call_and_output_status():
    output = (
        '{"ok":true,"name":"read","output":"","error":null,'
        '"metadata":{"path":"/repo/README.md"},"awaitUserResponse":false}'
    )

    assert format_tool_progress_summary("read README.md", output) == "read README.md  ok"


def test_format_tool_progress_summary_includes_failure_detail():
    output = (
        '{"ok":false,"name":"bash","output":"stderr","error":"Command exited with code 1.",'
        '"metadata":{"exitCode":1},"awaitUserResponse":false}'
    )

    assert (
        format_tool_progress_summary("bash pytest", output)
        == "bash pytest  failed - Command exited with code 1."
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
