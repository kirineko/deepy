from __future__ import annotations

import os
import sys
from pathlib import Path

from deepy.config import Settings
from deepy.llm.runner import run_prompt_once


def run_tui(
    settings: Settings,
    *,
    project_root: Path | None = None,
) -> int:
    """Run the Modern Textual UI."""
    os.environ.setdefault("TEXTUAL_DISABLE_KITTY_KEY", "1")
    try:
        from deepy.tui.app import DeepyTuiApp
    except Exception as exc:
        print(
            "Deepy Modern UI could not start. "
            "Run `deepy` with Classic UI or `deepy config setup` to update UI settings. "
            f"Reason: {exc}",
            file=sys.stderr,
        )
        return 1

    app = DeepyTuiApp(
        settings=settings,
        project_root=(project_root or Path.cwd()).resolve(),
        run_once=run_prompt_once,
        guide_missing_config=True,
    )
    app.run(mouse=True)
    if app.exit_summary_text:
        print(app.exit_summary_text)
    return 0
