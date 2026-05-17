from __future__ import annotations

import json

from rich.cells import cell_len
from rich.console import Console

from deepy.ui.message_view import MAX_DIFF_LINES
from deepy.ui.message_view import format_tool_output_summary
from deepy.ui.message_view import format_tool_progress_summary
from deepy.ui.message_view import format_tool_call_summary
from deepy.ui.message_view import format_tool_display_label
from deepy.ui.message_view import build_thinking_summary
from deepy.ui.message_view import build_tool_params_snippet
from deepy.ui.message_view import build_tool_result_snippet
from deepy.ui.message_view import DiffPreviewLine
from deepy.ui.message_view import is_invisible_execution
from deepy.ui.message_view import parse_diff_preview
from deepy.ui.message_view import parse_tool_output
from deepy.ui.message_view import render_diff_preview_line
from deepy.ui.message_view import render_message
from deepy.ui.message_view import render_shell_output_block
from deepy.ui.message_view import render_todo_board
from deepy.ui.message_view import render_tool_diff_preview
from deepy.ui.message_view import render_tool_output
from deepy.ui.message_view import tool_diff_preview
from deepy.ui.message_view import tool_diff_preview_lines
from deepy.ui.styles import DARK_PALETTE
from deepy.ui.styles import LIGHT_PALETTE


def test_format_tool_output_summary_uses_path_detail():
    output = (
        '{"ok":true,"name":"read","output":"","error":null,'
        '"metadata":{"path":"/tmp/a"},"awaitUserResponse":false}'
    )

    assert format_tool_output_summary(output) == "[Read] ok - /tmp/a"


def test_format_tool_output_summary_uses_error_detail():
    output = (
        '{"ok":false,"name":"shell","output":"stderr","error":"Command exited with code 1.",'
        '"metadata":{"exitCode":1},"awaitUserResponse":false}'
    )

    assert format_tool_output_summary(output) == "[Shell] failed - Command exited with code 1."


def test_parse_tool_output_preserves_pending_question_state():
    view = parse_tool_output(
        '{"ok":true,"name":"AskUserQuestion","output":"Waiting for user input.","error":null,'
        '"metadata":{"kind":"ask_user_question","questions":[{"question":"Choose one",'
        '"options":[{"label":"Yes"}]}]},"awaitUserResponse":true}'
    )

    assert view.name == "AskUserQuestion"
    assert view.await_user_response is True
    assert view.summary == "[AskUserQuestion] ok - Waiting for user input."


def test_format_tool_display_label_normalizes_protocol_names():
    assert format_tool_display_label("AskUserQuestion") == "[AskUserQuestion]"
    assert format_tool_display_label("WebFetch") == "[WebFetch]"
    assert format_tool_display_label("edit") == "[Modify]"
    assert format_tool_display_label("todo_write") == "[Todo]"


def test_todo_tool_params_snippet_hides_raw_json():
    snippet = build_tool_params_snippet(
        {
            "name": "todo_write",
            "arguments": json.dumps(
                {
                    "todos": [
                        {"id": "one", "content": "One", "status": "in_progress"},
                        {"id": "two", "content": "Two", "status": "pending"},
                    ]
                }
            ),
        }
    )

    assert snippet == "2 items"
    assert "content" not in snippet


def test_parse_tool_output_recognizes_todo_metadata():
    output = json.dumps(
        {
            "ok": True,
            "name": "todo_write",
            "output": "Todo list updated",
            "metadata": {
                "kind": "todo_list",
                "todos": [{"id": "one", "content": "One", "status": "in_progress"}],
                "counts": {"total": 1, "pending": 0, "in_progress": 1, "completed": 0},
            },
            "awaitUserResponse": False,
        }
    )

    view = parse_tool_output(output)

    assert view.name == "todo_write"
    assert view.metadata is not None
    assert view.metadata["kind"] == "todo_list"
    assert format_tool_progress_summary("[Todo] 1 item", output) == "[Todo] 1 item  ok - 0/1 - One"


def test_render_todo_board_shows_progress_and_current_task():
    output = json.dumps(
        {
            "ok": True,
            "name": "todo_write",
            "output": "Todo list updated",
            "metadata": {
                "kind": "todo_list",
                "todos": [
                    {"id": "one", "content": "Inspect code", "status": "completed"},
                    {"id": "two", "content": "Implement todo board", "status": "in_progress"},
                    {"id": "three", "content": "Run tests", "status": "pending"},
                ],
            },
            "awaitUserResponse": False,
        }
    )
    console = Console(record=True, width=60, color_system=None)

    board = render_todo_board(output, palette=DARK_PALETTE, width=60)
    assert board is not None
    console.print(board)
    rendered = console.export_text()

    assert "Todo List 1/3" in rendered
    assert "Current: Implement todo board" in rendered
    assert "[x] Inspect code" in rendered
    assert "[*] Implement todo board" in rendered
    assert "[ ] Run tests" in rendered


def test_raw_tool_output_is_truncated():
    summary = format_tool_output_summary("x" * 200)

    assert summary.endswith("... [truncated]")
    assert len(summary) <= 160


def test_parse_tool_output_normalizes_mcp_content_array():
    output = json.dumps(
        [
            {
                "type": "input_text",
                "text": "Detailed Results:\n\nTitle: Result One\nURL: https://example.com",
            }
        ]
    )

    view = parse_tool_output(output)

    assert view.name == "mcp"
    assert view.ok is True
    assert view.status == "ok"
    assert view.summary == "[MCP] ok - Detailed Results:"
    assert "Title: Result One" in view.output


def test_parse_tool_output_normalizes_mcp_call_tool_result_dict():
    output = json.dumps(
        {
            "content": [{"type": "text", "text": "Result body"}],
            "isError": False,
        }
    )

    view = parse_tool_output(output)

    assert view.name == "mcp"
    assert view.ok is True
    assert view.status == "ok"
    assert view.output == "Result body"


def test_parse_tool_output_normalizes_single_mcp_content_block():
    output = json.dumps(
        {
            "type": "input_text",
            "text": "Detailed Results:\n\nTitle: Single Block",
        }
    )

    view = parse_tool_output(output)

    assert view.name == "mcp"
    assert view.ok is True
    assert view.status == "ok"
    assert view.summary == "[MCP] ok - Detailed Results:"
    assert "Title: Single Block" in view.output


def test_parse_tool_output_normalizes_mcp_is_error_snake_case():
    output = json.dumps(
        {
            "content": {"type": "text", "text": "MCP failed"},
            "is_error": True,
        }
    )

    view = parse_tool_output(output)

    assert view.name == "mcp"
    assert view.ok is False
    assert view.status == "failed"
    assert view.error == "MCP failed"


def test_parse_tool_output_marks_mcp_is_error_without_text_as_failed():
    output = json.dumps(
        {
            "content": {"type": "image", "image_url": "data:image/png;base64,abc"},
            "isError": True,
        }
    )

    view = parse_tool_output(output)

    assert view.name == "mcp"
    assert view.ok is False
    assert view.status == "failed"
    assert view.error == "1 content block"


def test_parse_tool_output_marks_non_text_mcp_content_as_ok():
    output = json.dumps(
        {
            "type": "image",
            "image_url": "data:image/png;base64,abc",
        }
    )

    view = parse_tool_output(output)

    assert view.name == "mcp"
    assert view.ok is True
    assert view.status == "ok"
    assert view.summary == "[MCP] ok - 1 content block"


def test_parse_tool_output_marks_mcp_structured_content_as_ok():
    output = json.dumps({"structuredContent": {"result": "ok"}, "isError": False})

    view = parse_tool_output(output)

    assert view.name == "mcp"
    assert view.ok is True
    assert view.status == "ok"
    assert view.summary == "[MCP] ok - structured content"


def test_parse_tool_output_normalizes_sdk_tool_error_string():
    output = (
        "An error occurred while running the tool. Please try again. "
        "Error: Timed out while waiting for response to ClientRequest."
    )

    view = parse_tool_output(output)

    assert view.ok is False
    assert view.status == "failed"
    assert view.error == output
    assert view.summary.startswith("[Tool] failed - An error occurred")


def test_parse_tool_output_leaves_unrecognized_json_array_raw():
    view = parse_tool_output(json.dumps(["plain", "array"]))

    assert view.ok is None
    assert view.status == "raw"


def test_format_tool_progress_summary_marks_mcp_content_as_ok():
    output = json.dumps(
        [
            {
                "type": "input_text",
                "text": "Detailed Results:\n\nTitle: Result One",
            }
        ]
    )

    assert (
        format_tool_progress_summary("[McpTavilyTavilySearch] Vibe Coding", output)
        == "[McpTavilyTavilySearch] Vibe Coding  ok"
    )


def test_format_tool_progress_summary_marks_sdk_tool_error_as_failed():
    output = (
        "An error occurred while running the tool. Please try again. "
        "Error: Timed out while waiting for response to ClientRequest."
    )

    assert (
        format_tool_progress_summary("[McpTavilyTavilySearch] Vibe Coding", output)
        == "[McpTavilyTavilySearch] Vibe Coding  failed - "
        "An error occurred while running the tool. Please try again. "
        "Error: Timed out while waiting for response to ClientRequest."
    )


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
    assert "[Modify] ok - file" in rendered
    assert "[Modify] file (+1 -0)" in rendered
    assert "new" in rendered
    assert "+new" not in rendered


def test_render_tool_output_shows_write_preview_with_diff_style():
    output = (
        '{"ok":true,"name":"write","output":"Wrote file","error":null,'
        '"metadata":{"path":"file","diff":"--- /dev/null\\n+++ b/file\\n@@ -0,0 +1,1 @@\\n+new\\n"},'
        '"awaitUserResponse":false}'
    )
    console = Console(record=True, width=120)

    console.print(render_tool_output(output, width=40))

    rendered = console.export_text()
    assert "[Write] ok - file" in rendered
    assert "[Write] file (+1 -0)" in rendered
    assert "new" in rendered
    assert "+ new" in rendered


def test_render_tool_output_bolds_tool_label():
    output = json.dumps(
        {
            "ok": True,
            "name": "WebFetch",
            "output": "Fetched page",
            "error": None,
            "metadata": {},
            "awaitUserResponse": False,
        }
    )

    rendered = render_tool_output(output)
    summary = list(rendered.renderables)[0]

    assert summary.plain.startswith("[WebFetch] ok")
    assert "bold" in str(summary.spans[0].style)
    assert "underline" in str(summary.spans[0].style)


def test_render_tool_output_includes_full_shell_output_block():
    output = json.dumps(
        {
            "ok": True,
            "name": "shell",
            "output": "line 1\nline 2\nline 3",
            "error": None,
            "metadata": {"exitCode": 0},
            "awaitUserResponse": False,
        }
    )
    console = Console(record=True, width=120)

    console.print(render_tool_output(output))

    rendered = console.export_text()
    assert "[Shell] ok - line 1" in rendered
    assert "[Shell]" in rendered
    assert "line 1" in rendered
    assert "line 2" in rendered
    assert "line 3" in rendered


def test_render_shell_output_block_uses_plain_tool_text_without_background():
    output = json.dumps(
        {
            "ok": True,
            "name": "shell",
            "output": "line 1",
            "error": None,
            "metadata": {"exitCode": 0},
            "awaitUserResponse": False,
        }
    )

    panel = render_shell_output_block(output, palette=DARK_PALETTE)

    assert panel is not None
    assert panel.renderable.style == DARK_PALETTE.tool
    assert " on " not in str(panel.renderable.style)


def test_render_shell_output_block_ignores_non_shell_tools():
    output = json.dumps(
        {
            "ok": True,
            "name": "read",
            "output": "file content",
            "error": None,
            "metadata": {},
            "awaitUserResponse": False,
        }
    )

    assert render_shell_output_block(output) is None


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
    assert "[Modify] file (+1 -1)" in rendered
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
        DiffPreviewLine(marker="-", content="old", kind="removed", old_lineno=12),
        width=24,
    )
    added = render_diff_preview_line(
        DiffPreviewLine(marker="+", content="new", kind="added", new_lineno=13),
        width=24,
    )

    assert removed.plain == "  12      - old" + " " * 9
    assert added.plain == "       13 + new" + " " * 9
    assert cell_len(removed.plain) == 24
    assert cell_len(added.plain) == 24
    assert "#4a2528" in str(removed.spans)
    assert "#1f3d2b" in str(added.spans)
    assert "#fca5a5" in str(removed.spans)
    assert "#86efac" in str(added.spans)


def test_render_diff_preview_line_pads_by_display_cells_for_wide_characters():
    added = render_diff_preview_line(
        DiffPreviewLine(marker="+", content="变量", kind="added", new_lineno=1),
        width=18,
    )

    assert cell_len(added.plain) == 18
    assert added.plain.endswith("  ")


def test_render_diff_preview_line_uses_light_theme_contrast():
    removed = render_diff_preview_line(
        DiffPreviewLine(marker="-", content="old", kind="removed", old_lineno=12),
        palette=LIGHT_PALETTE,
        width=24,
    )
    added = render_diff_preview_line(
        DiffPreviewLine(marker="+", content="new", kind="added", new_lineno=13),
        palette=LIGHT_PALETTE,
        width=24,
    )

    assert cell_len(removed.plain) == 24
    assert cell_len(added.plain) == 24
    assert "#fef2f2" in str(removed.spans)
    assert "#ecfdf5" in str(added.spans)
    assert "#b91c1c" in str(removed.spans)
    assert "#047857" in str(added.spans)


def test_render_write_preview_line_uses_shared_diff_background():
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
    rendered = render_tool_diff_preview(output, width=40)
    assert rendered is not None
    lines = list(rendered.renderables)

    assert "[Write] file (+1 -0)" in lines[0].plain
    assert lines[1].plain.startswith("        1 + let x = 1;")
    assert cell_len(lines[1].plain) == 40
    assert "#1f3d2b" in str(lines[1].spans)


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
    rendered = render_tool_diff_preview(output, palette=LIGHT_PALETTE, width=40)
    assert rendered is not None
    lines = list(rendered.renderables)

    assert cell_len(lines[1].plain) == 40
    assert "#ecfdf5" in str(lines[1].spans)


def test_render_write_preview_line_uses_dark_theme_background():
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
    rendered = render_tool_diff_preview(output, palette=DARK_PALETTE, width=40)
    assert rendered is not None
    lines = list(rendered.renderables)

    assert cell_len(lines[1].plain) == 40
    assert "#1f3d2b" in str(lines[1].spans)


def test_render_tool_diff_preview_highlights_programming_language_content():
    output = json.dumps(
        {
            "ok": True,
            "name": "edit",
            "output": "Edited file",
            "error": None,
            "metadata": {
                "path": "sample.py",
                "diff": "--- a/sample.py\n+++ b/sample.py\n@@ -1,1 +1,1 @@\n"
                "-def old(value):\n+def new(value):\n",
            },
            "awaitUserResponse": False,
        }
    )
    rendered = render_tool_diff_preview(output, width=64)
    assert rendered is not None
    lines = list(rendered.renderables)

    removed_spans = str(lines[1].spans)
    added_spans = str(lines[2].spans)
    assert "#66d9ef" in removed_spans
    assert "#66d9ef" in added_spans
    assert "#272822" not in removed_spans
    assert "#272822" not in added_spans
    assert "#4a2528" in removed_spans
    assert "#1f3d2b" in added_spans
    assert cell_len(lines[1].plain) == 64
    assert cell_len(lines[2].plain) == 64


def test_render_tool_diff_preview_preserves_light_diff_background_with_syntax():
    output = json.dumps(
        {
            "ok": True,
            "name": "edit",
            "output": "Edited file",
            "error": None,
            "metadata": {
                "path": "src/lib.rs",
                "diff": "--- a/src/lib.rs\n+++ b/src/lib.rs\n@@ -1,1 +1,1 @@\n"
                "-fn old_name() {}\n+fn new_name() {}\n",
            },
            "awaitUserResponse": False,
        }
    )
    rendered = render_tool_diff_preview(output, palette=LIGHT_PALETTE, width=64)
    assert rendered is not None
    lines = list(rendered.renderables)

    removed_spans = str(lines[1].spans)
    added_spans = str(lines[2].spans)
    assert "#fef2f2" in removed_spans
    assert "#ecfdf5" in added_spans
    assert "#272822" not in removed_spans
    assert "#272822" not in added_spans
    assert cell_len(lines[1].plain) == 64
    assert cell_len(lines[2].plain) == 64


def test_render_write_preview_does_not_truncate_large_writes():
    line_count = MAX_DIFF_LINES + 10
    body = "\n".join(f"+line {index}" for index in range(1, line_count + 1))
    output = json.dumps(
        {
            "ok": True,
            "name": "write",
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": "file",
                "diff": f"--- /dev/null\n+++ b/file\n@@ -0,0 +{line_count},{line_count} @@\n{body}\n",
            },
            "awaitUserResponse": False,
        }
    )
    console = Console(record=True, width=120)

    console.print(render_tool_diff_preview(output))

    rendered = console.export_text()
    assert "line 1" in rendered
    assert f"line {line_count}" in rendered
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
    console.print(
        render_message({"role": "system", "content": "Earlier conversation was compacted."})
    )

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

    assert "[Read] ok - file" in console.export_text()


def test_parse_diff_preview_removes_headers_and_classifies_lines():
    lines = parse_diff_preview(
        "--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n context\n-old\n+new"
    )

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


def test_build_tool_params_snippet_formats_shell_command_and_description():
    assert (
        build_tool_params_snippet(
            {"name": "shell", "arguments": '{"command":"pytest","description":"run tests"}'}
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
        == "[Read] README.md"
    )


def test_format_tool_call_summary_formats_write_without_content_body():
    summary = format_tool_call_summary(
        "write",
        json.dumps(
            {
                "file_path": "/repo/src/lib.rs",
                "content": 'fn main() {\n    println!("hi");\n}\n',
            }
        ),
        project_root="/repo",
    )

    assert summary == "[Write] src/lib.rs (4 lines, 34 chars)"
    assert "println" not in summary


def test_format_tool_call_summary_formats_modify_create_without_content_body():
    summary = format_tool_call_summary(
        "modify",
        json.dumps(
            {
                "file_path": "/repo/src/lib.rs",
                "content": 'fn main() {\n    println!("hi");\n}\n',
            }
        ),
        project_root="/repo",
    )

    assert summary == "[Modify] src/lib.rs (4 lines, 34 chars)"
    assert "println" not in summary


def test_format_tool_call_summary_hides_ask_user_question_arguments():
    summary = format_tool_call_summary(
        "AskUserQuestion",
        json.dumps(
            {
                "questions": [
                    {
                        "question": "Which path?",
                        "options": [{"label": "fast"}, {"label": "thorough"}],
                    }
                ]
            }
        ),
    )

    assert summary == "[AskUserQuestion]"
    assert "Which path?" not in summary
    assert "questions" not in summary


def test_format_tool_progress_summary_merges_call_and_output_status():
    output = (
        '{"ok":true,"name":"read","output":"","error":null,'
        '"metadata":{"path":"/repo/README.md"},"awaitUserResponse":false}'
    )

    assert format_tool_progress_summary("[Read] README.md", output) == "[Read] README.md  ok"


def test_format_tool_progress_summary_includes_failure_detail():
    output = (
        '{"ok":false,"name":"shell","output":"stderr","error":"Command exited with code 1.",'
        '"metadata":{"exitCode":1},"awaitUserResponse":false}'
    )

    assert (
        format_tool_progress_summary("shell pytest", output)
        == "shell pytest  failed - Command exited with code 1."
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
    content = json.dumps({"ok": True, "name": "shell", "output": "x" * 2_010})

    snippet = build_tool_result_snippet(content)

    assert snippet.startswith("x" * 2_000)
    assert snippet.endswith("... (total 2010 chars)")


def test_is_invisible_execution_detects_failed_shell_payload():
    assert is_invisible_execution(json.dumps({"ok": False, "name": "shell"})) is True
    assert is_invisible_execution(json.dumps({"ok": True, "name": "shell"})) is False
    assert is_invisible_execution(json.dumps({"ok": False, "name": "read"})) is False
