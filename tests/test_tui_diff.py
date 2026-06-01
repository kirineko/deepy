from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.cells import cell_len
from textual.app import App, ComposeResult

from deepy.tui.diff import (
    diff_view_from_tool_output,
    render_unified_diff_rich,
    render_unified_diff_text,
)
from deepy.tui.widgets import DiffBlock


def _tool_output(diff: str, *, name: str = "Write", path: str = "src/app.py") -> str:
    return json.dumps(
        {
            "ok": True,
            "name": name,
            "output": "Wrote file",
            "error": None,
            "metadata": {
                "path": path,
                "diff": diff,
                "diff_preview": diff,
            },
            "awaitUserResponse": False,
        }
    )


def _write_output(diff: str) -> str:
    return _tool_output(diff)


def test_tui_diff_model_renders_unified_preview() -> None:
    output = _write_output("--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n")

    view = diff_view_from_tool_output(output)

    assert view is not None
    assert view.path == "src/app.py"
    assert view.added == 1
    assert view.removed == 1
    rendered = render_unified_diff_text(view)
    assert "src/app.py (+1 -1)" in rendered
    assert "- old" in rendered
    assert "+ new" in rendered


def test_tui_diff_model_recognizes_Update_outputs() -> None:
    output = _tool_output(
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n",
        name="Update",
    )

    view = diff_view_from_tool_output(output)

    assert view is not None
    assert view.tool_name == "Update"
    assert view.path == "src/app.py"
    assert view.added == 1
    assert view.removed == 1


def test_tui_diff_model_keeps_multi_file_sections() -> None:
    output = _tool_output(
        "--- a/index.html\n+++ b/index.html\n@@ -1 +1 @@\n-old html\n+new html\n"
        "--- a/main.js\n+++ b/main.js\n@@ -1 +1 @@\n-old js\n+new js\n",
        name="Update",
        path="2 files",
    )

    view = diff_view_from_tool_output(output)

    assert view is not None
    assert view.path == "2 files"
    assert view.added == 2
    assert view.removed == 2
    assert [section.path for section in view.sections] == ["index.html", "main.js"]
    rendered = render_unified_diff_text(view)
    assert "index.html (+1 -1)" in rendered
    assert "main.js (+1 -1)" in rendered
    assert "2 files (+2 -2)" not in rendered


def test_tui_diff_rich_rendering_uses_diff_colors_and_syntax() -> None:
    output = _tool_output(
        "--- a/sample.py\n+++ b/sample.py\n@@ -1,1 +1,1 @@\n"
        "-def old(value):\n+def new(value):\n",
        path="sample.py",
    )
    view = diff_view_from_tool_output(output)

    assert view is not None
    rendered = render_unified_diff_rich(view, width=64)
    lines = list(rendered.renderables)

    removed_spans = str(lines[1].spans)
    added_spans = str(lines[2].spans)
    assert "#66d9ef" in removed_spans
    assert "#66d9ef" in added_spans
    assert "#4a2528" in removed_spans
    assert "#1f3d2b" in added_spans
    assert cell_len(lines[1].plain) == 64
    assert cell_len(lines[2].plain) == 64


def test_tui_diff_rich_rendering_highlights_multiline_xml_syntax() -> None:
    output = _tool_output(
        "--- /dev/null\n+++ b/pom.xml\n@@ -0,0 +1,6 @@\n"
        "+<dependency\n"
        '+    groupId="com.example">\n'
        "+</dependency>\n"
        "+<!--\n"
        "+  comment text\n"
        "+-->\n",
        path="pom.xml",
    )
    view = diff_view_from_tool_output(output)

    assert view is not None
    rendered = render_unified_diff_rich(view, width=96)
    lines = list(rendered.renderables)

    attribute_spans = str(lines[2].spans)
    comment_spans = str(lines[5].spans)
    assert "#a6e22e" in attribute_spans
    assert "#e6db74" in attribute_spans
    assert "#1f3d2b" in attribute_spans
    assert "#959077" in comment_spans
    assert "#1f3d2b" in comment_spans


def test_tui_diff_rich_rendering_uses_xml_for_xml_like_paths() -> None:
    output = _tool_output(
        "--- a/icon.svg\n+++ b/icon.svg\n@@ -1,1 +1,1 @@\n"
        '-<svg viewBox="0 0 10 10"></svg>\n'
        '+<svg viewBox="0 0 12 12"></svg>\n',
        path="icon.svg",
    )
    view = diff_view_from_tool_output(output)

    assert view is not None
    rendered = render_unified_diff_rich(view, width=96)
    lines = list(rendered.renderables)

    assert "#ff4689" in str(lines[1].spans)
    assert "#4a2528" in str(lines[1].spans)
    assert "#a6e22e" in str(lines[2].spans)
    assert "#e6db74" in str(lines[2].spans)
    assert "#1f3d2b" in str(lines[2].spans)


def test_tui_diff_rich_rendering_preserves_non_xml_syntax() -> None:
    output = _tool_output(
        "--- a/sample.py\n+++ b/sample.py\n@@ -1,1 +1,1 @@\n"
        "-def old(value):\n+def new(value):\n",
        path="sample.py",
    )
    view = diff_view_from_tool_output(output)

    assert view is not None
    rendered = render_unified_diff_rich(view, width=64)
    lines = list(rendered.renderables)

    assert "#66d9ef" in str(lines[2].spans)
    assert "#1f3d2b" in str(lines[2].spans)
    assert "#272822" not in str(lines[2].spans)


def test_tui_diff_rich_rendering_wraps_to_narrow_and_wide_widths() -> None:
    output = _tool_output(
        "--- a/sample.py\n+++ b/sample.py\n@@ -1,1 +1,1 @@\n"
        "-old_value = 'abcdefghijklmnopqrstuvwxyz'\n"
        "+new_value = 'abcdefghijklmnopqrstuvwxyz'\n",
        path="sample.py",
    )
    view = diff_view_from_tool_output(output)

    assert view is not None
    narrow_lines = list(render_unified_diff_rich(view, width=32).renderables)
    wide_lines = list(render_unified_diff_rich(view, width=120).renderables)
    assert cell_len(narrow_lines[1].plain) == 32
    assert cell_len(narrow_lines[2].plain) == 32
    assert cell_len(wide_lines[1].plain) == 120
    assert cell_len(wide_lines[2].plain) == 120


def test_tui_diff_model_compacts_large_diffs() -> None:
    diff = "--- a/file\n+++ b/file\n@@ -0,0 +1,150 @@\n" + "\n".join(
        f"+line {index}" for index in range(150)
    )

    view = diff_view_from_tool_output(_write_output(diff), max_lines=12)

    assert view is not None
    assert view.truncated is True
    assert len(view.lines) == 12
    assert render_unified_diff_text(view).endswith("... diff truncated ...")


def test_tui_diff_tracks_hunks_and_block_navigation() -> None:
    output = _write_output(
        "--- a/src/app.py\n+++ b/src/app.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        "@@ -10 +10 @@\n-before\n+after\n"
    )
    view = diff_view_from_tool_output(output)

    assert view is not None
    assert view.hunks == ("@@ -1 +1 @@", "@@ -10 +10 @@")


class _DiffBlockTestApp(App[None]):
    def __init__(self, block: DiffBlock) -> None:
        super().__init__()
        self.block = block

    def compose(self) -> ComposeResult:
        yield self.block


@pytest.mark.asyncio
async def test_tui_diff_block_navigates_and_folds_hunks() -> None:
    output = _write_output(
        "--- a/src/app.py\n+++ b/src/app.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        "@@ -10 +10 @@\n-before\n+after\n"
    )
    view = diff_view_from_tool_output(output)

    assert view is not None
    app = _DiffBlockTestApp(DiffBlock(view, width=40))
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        block = app.query_one(DiffBlock)
        block.focus()
        assert block.current_hunk == 0

        await pilot.press("n")
        await pilot.pause()
        assert block.current_hunk == 1

        await pilot.press("p")
        await pilot.pause()
        assert block.current_hunk == 0

        await pilot.press("f")
        await pilot.pause()
        assert block.folded is True
        app.exit()


def test_tui_diff_does_not_import_reference_packages() -> None:
    package_root = Path(__file__).resolve().parents[1] / "src" / "deepy" / "tui"
    checked_files = [
        path
        for path in package_root.glob("*.py")
        if path.name not in {"compat.py", "__init__.py"}
    ]

    assert checked_files
    for path in checked_files:
        text = path.read_text(encoding="utf-8")
        assert "import toad" not in text
        assert "from toad" not in text
        assert "textual_diff_view" not in text
        assert "textual-diff-view" not in text
