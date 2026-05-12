from __future__ import annotations

from pathlib import Path

AGENT_DRIFT_GUARD = (
    "Keep the latest user task in focus; preserve explicit constraints, paths, commands, "
    "test results, and decisions when compressing context."
)


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
