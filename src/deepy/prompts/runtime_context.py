from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from deepy.tools.shell_utils import detect_runtime_environment

IGNORED_TOP_LEVEL_ENTRIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "wheels",
}


def build_runtime_context(project_root: Path, *, include_git_dirty: bool = True) -> str:
    runtime_environment = detect_runtime_environment()
    lines = [f"Project root: {project_root}"]
    lines.append(f"Current working directory: {Path.cwd()}")
    lines.append(f"Home directory: {Path.home()}")
    lines.append(f"System: {platform.platform()}")
    lines.append(f"Shell: {runtime_environment.shell_path}")
    lines.append("Runtime environment:")
    lines.append(f"- OS family: {runtime_environment.os_family}")
    lines.append(f"- Shell kind: {runtime_environment.shell_kind}")
    lines.append(f"- Command dialect: {runtime_environment.command_dialect}")
    lines.append(f"- Path style: {runtime_environment.path_style}")
    lines.append(f"Python: {_python_info()}")
    node = _command_output(project_root, ["node", "--version"])
    lines.append(f"Node: {node or 'missing'}")
    lines.append("Tool availability:")
    lines.extend(f"- {tool}: {_tool_info(tool, project_root)}" for tool in ("rg", "jq", "ast-grep"))
    branch = _git_output(project_root, ["git", "branch", "--show-current"])
    if branch:
        lines.append(f"Git branch: {branch}")
    if include_git_dirty:
        status = _git_output(project_root, ["git", "status", "--short"])
        lines.append(f"Git dirty: {'yes' if status else 'no'}")
    top_level = _top_level_entries(project_root)
    if top_level:
        lines.append("Top-level entries:")
        lines.extend(f"- {entry}" for entry in top_level)
    return "\n".join(lines)


def _python_info() -> str:
    version = ".".join(str(part) for part in sys.version_info[:3])
    return f"{sys.executable} ({version})"


def _tool_info(tool: str, cwd: Path) -> str:
    path = shutil.which(tool)
    if path is None:
        return "missing"
    version = _command_output(cwd, [path, "--version"])
    first_line = version.splitlines()[0] if version else ""
    return f"{path}" + (f" ({first_line})" if first_line else "")


def _command_output(project_root: Path, args: list[str]) -> str:
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


def _git_output(project_root: Path, args: list[str]) -> str:
    return _command_output(project_root, args)


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
