from __future__ import annotations

import sys
from pathlib import Path

from deepy.config import Settings
from deepy.llm.runner import run_prompt_once


def run_tui(
    settings: Settings,
    *,
    project_root: Path | None = None,
) -> int:
    """Run the experimental Textual TUI."""
    try:
        from deepy.tui.app import DeepyTuiApp
    except Exception as exc:
        print(
            "Deepy experimental TUI could not start. "
            "Run `deepy` for the stable terminal UI. "
            f"Reason: {exc}",
            file=sys.stderr,
        )
        return 1

    app = DeepyTuiApp(
        settings=settings,
        project_root=(project_root or Path.cwd()).resolve(),
        run_once=run_prompt_once,
    )
    app.run()
    return 0
