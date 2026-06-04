from __future__ import annotations

from deepy.ui.classic.markdown import MarkdownSegment
from deepy.ui.classic.markdown import render_inline_line
from deepy.ui.classic.markdown import render_markdown
from deepy.ui.classic.markdown import split_by_fences


def test_render_markdown_returns_empty_text_for_empty_input():
    assert render_markdown("").plain == ""


def test_render_markdown_preserves_heading_text():
    result = render_markdown("# Title").plain

    assert "Title" in result
    assert "#" not in result


def test_render_markdown_preserves_code_fences_with_language_tag():
    result = render_markdown("```js\nconsole.log(1);\n```")

    assert "console.log(1);" in result.plain
    assert "```" not in result.plain
    assert len({str(span.style) for span in result.spans}) > 1


def test_render_markdown_highlights_rust_code_blocks():
    result = render_markdown("```rust\nimpl Solution {\n    pub fn solve() {}\n}\n```")

    assert "impl Solution" in result.plain
    assert "pub fn solve" in result.plain
    assert len({str(span.style) for span in result.spans}) > 1


def test_render_markdown_rebases_xml_code_block_background():
    result = render_markdown('```xml\n<root name="demo">value</root>\n```', width=80)
    spans = str(result.spans)

    assert "#ff4689" in spans
    assert "#a6e22e" in spans
    assert "#e6db74" in spans
    assert "#1f2430" in spans
    assert "#272822" not in spans


def test_render_markdown_uses_xml_highlighting_for_svg_code_blocks():
    result = render_markdown('```svg\n<svg viewBox="0 0 10 10"></svg>\n```', width=80)
    spans = str(result.spans)

    assert "#ff4689" in spans
    assert "#a6e22e" in spans
    assert "#e6db74" in spans
    assert "#1f2430" in spans


def test_render_markdown_styles_inline_code_without_removing_it():
    result = render_markdown("Use `npm install` first.").plain

    assert "npm install" in result
    assert "`" not in result


def test_render_markdown_renders_bullets():
    result = render_markdown("- item one\n- item two").plain

    assert "• item one" in result
    assert "• item two" in result


def test_render_markdown_handles_plain_text_unchanged():
    text = "hello world\nthis is a sentence"

    assert render_markdown(text).plain == text


def test_render_markdown_formats_pipe_tables():
    result = render_markdown(
        "| Name | Role |\n"
        "| --- | --- |\n"
        "| Deepy | Terminal Agent |\n"
        "| Search | Web fallback |"
    ).plain

    assert "┌" in result
    assert "┬" in result
    assert "Name" in result
    assert "Terminal Agent" in result
    assert "| --- | --- |" not in result


def test_render_markdown_wraps_wide_table_cells_to_fit_width():
    result = render_markdown(
        "| Item | Detail |\n"
        "| --- | --- |\n"
        "| Markdown | This cell contains a long explanation that should wrap cleanly |",
        width=42,
    ).plain

    table_lines = [line for line in result.splitlines() if line.startswith(("┌", "│", "├", "└"))]
    assert table_lines
    assert all(len(line) <= 42 for line in table_lines)
    assert "long" in result
    assert "wrap" in result


def test_render_markdown_formats_horizontal_rules():
    result = render_markdown("before\n---\nafter", width=32).plain

    assert "before" in result
    assert "─" * 32 in result
    assert "after" in result


def test_split_by_fences_handles_unclosed_code_block():
    segments = split_by_fences("before\n```py\nprint(1)")

    assert segments == [
        MarkdownSegment(kind="text", body="before"),
        MarkdownSegment(kind="code", lang="py", body="print(1)"),
    ]


def test_render_inline_line_formats_numbered_lists_and_quotes():
    assert render_inline_line("1. **first**").plain == "1. first"
    assert render_inline_line("> _quoted_").plain == "| quoted"
