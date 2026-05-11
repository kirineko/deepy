from __future__ import annotations

import subprocess
from pathlib import Path

IGNORED_TOP_LEVEL_ENTRIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "reference",
    "spec",
}


def build_runtime_context(project_root: Path) -> str:
    lines = [f"Project root: {project_root}"]
    branch = _git_output(project_root, ["git", "branch", "--show-current"])
    if branch:
        lines.append(f"Git branch: {branch}")
    status = _git_output(project_root, ["git", "status", "--short"])
    lines.append(f"Git dirty: {'yes' if status else 'no'}")
    top_level = _top_level_entries(project_root)
    if top_level:
        lines.append("Top-level entries:")
        lines.extend(f"- {entry}" for entry in top_level)
    return "\n".join(lines)


def _git_output(project_root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _top_level_entries(project_root: Path, limit: int = 30) -> list[str]:
    try:
        entries = sorted(project_root.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    except OSError:
        return []
    names: list[str] = []
    for entry in entries:
        if entry.name in IGNORED_TOP_LEVEL_ENTRIES:
            continue
        names.append(f"{entry.name}/" if entry.is_dir() else entry.name)
        if len(names) >= limit:
            break
    return names
