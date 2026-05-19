from __future__ import annotations

import json
from pathlib import Path

from rich.cells import cell_len

from deepy.tui.diff import (
    diff_view_from_tool_output,
    render_unified_diff_rich,
    render_unified_diff_text,
)


def _tool_output(diff: str, *, name: str = "write", path: str = "src/app.py") -> str:
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


def test_tui_diff_model_recognizes_modify_outputs() -> None:
    output = _tool_output(
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n",
        name="modify",
    )

    view = diff_view_from_tool_output(output)

    assert view is not None
    assert view.tool_name == "modify"
    assert view.path == "src/app.py"
    assert view.added == 1
    assert view.removed == 1


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


def test_tui_diff_model_compacts_large_diffs() -> None:
    diff = "--- a/file\n+++ b/file\n@@ -0,0 +1,150 @@\n" + "\n".join(
        f"+line {index}" for index in range(150)
    )

    view = diff_view_from_tool_output(_write_output(diff), max_lines=12)

    assert view is not None
    assert view.truncated is True
    assert len(view.lines) == 12
    assert render_unified_diff_text(view).endswith("... diff truncated ...")


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
