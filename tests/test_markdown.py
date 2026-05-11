from __future__ import annotations

from deepy.ui.markdown import MarkdownSegment
from deepy.ui.markdown import render_inline_line
from deepy.ui.markdown import render_markdown
from deepy.ui.markdown import split_by_fences


def test_render_markdown_returns_empty_text_for_empty_input():
    assert render_markdown("").plain == ""


def test_render_markdown_preserves_heading_text():
    result = render_markdown("# Title").plain

    assert "Title" in result
    assert "#" in result


def test_render_markdown_preserves_code_fences_with_language_tag():
    result = render_markdown("```js\nconsole.log(1);\n```").plain

    assert "[js]" in result
    assert "console.log(1);" in result


def test_render_markdown_styles_inline_code_without_removing_it():
    result = render_markdown("Use `npm install` first.").plain

    assert "npm install" in result
    assert "`" not in result


def test_render_markdown_keeps_bullet_markers():
    result = render_markdown("- item one\n- item two").plain

    assert "- item one" in result
    assert "- item two" in result


def test_render_markdown_handles_plain_text_unchanged():
    text = "hello world\nthis is a sentence"

    assert render_markdown(text).plain == text


def test_split_by_fences_handles_unclosed_code_block():
    segments = split_by_fences("before\n```py\nprint(1)")

    assert segments == [
        MarkdownSegment(kind="text", body="before"),
        MarkdownSegment(kind="code", lang="py", body="print(1)"),
    ]


def test_render_inline_line_formats_numbered_lists_and_quotes():
    assert render_inline_line("1. **first**").plain == "1. first"
    assert render_inline_line("> _quoted_").plain == "| quoted"
