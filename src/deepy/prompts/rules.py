from __future__ import annotations

from pathlib import Path

AGENT_DRIFT_GUARD = """Keep the user's current task and latest instructions in focus.
When the conversation is long, preserve explicit constraints, file paths, commands, test results,
and decisions before compressing incidental discussion."""


def load_project_rules(project_root: Path, *, home: Path | None = None) -> str:
    home_dir = home or Path.home()
    candidates = [
        project_root / "AGENTS.md",
        home_dir / ".deepy" / "AGENTS.md",
    ]
    blocks: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            blocks.append(f"From {path}:\n{text}")
    return "\n\n".join(blocks)
