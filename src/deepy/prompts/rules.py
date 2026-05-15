from __future__ import annotations

from pathlib import Path

AGENTS_MD_MAX_BYTES = 32 * 1024

AGENT_DRIFT_GUARD = (
    "Keep the latest user task in focus; preserve explicit constraints, paths, commands, "
    "test results, and decisions when compressing context."
)


def load_project_rules(
    project_root: Path,
    *,
    home: Path | None = None,
    max_bytes: int = AGENTS_MD_MAX_BYTES,
) -> str:
    return load_agents_instructions(project_root, home=home, max_bytes=max_bytes)


def load_agents_instructions(
    work_dir: Path,
    *,
    home: Path | None = None,
    max_bytes: int = AGENTS_MD_MAX_BYTES,
) -> str:
    work_dir = work_dir.expanduser().resolve()
    home_dir = home or Path.home()

    discovered: list[tuple[Path, str]] = []
    global_path = _exact_file_path(home_dir / ".deepy", "AGENTS.md")
    if global_path is not None:
        text = _read_instruction_file(global_path)
        if text:
            discovered.append((global_path, text))

    git_root = find_git_root(work_dir)
    for directory in _dirs_root_to_leaf(git_root, work_dir):
        project_path = _exact_file_path(directory, "AGENTS.md")
        if project_path is None:
            continue
        text = _read_instruction_file(project_path)
        if text:
            discovered.append((project_path, text))

    return _merge_instruction_blocks(discovered, max_bytes=max_bytes)


def has_agents_instructions(work_dir: Path, *, home: Path | None = None) -> bool:
    work_dir = work_dir.expanduser().resolve()
    home_dir = home or Path.home()

    global_path = _exact_file_path(home_dir / ".deepy", "AGENTS.md")
    if global_path is not None and _read_instruction_file(global_path):
        return True

    git_root = find_git_root(work_dir)
    for directory in _dirs_root_to_leaf(git_root, work_dir):
        project_path = _exact_file_path(directory, "AGENTS.md")
        if project_path is not None and _read_instruction_file(project_path):
            return True
    return False


def find_git_root(work_dir: Path) -> Path:
    current = work_dir.expanduser().resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return work_dir.expanduser().resolve()
        current = parent


def _dirs_root_to_leaf(root: Path, leaf: Path) -> list[Path]:
    root = root.resolve()
    current = leaf.resolve()
    directories: list[Path] = []
    while True:
        directories.append(current)
        if current == root:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    directories.reverse()
    return directories


def _exact_file_path(directory: Path, filename: str) -> Path | None:
    try:
        for child in directory.iterdir():
            if child.name == filename and child.is_file():
                return child
    except OSError:
        return None
    return None


def _read_instruction_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _merge_instruction_blocks(
    discovered: list[tuple[Path, str]],
    *,
    max_bytes: int,
) -> str:
    if not discovered or max_bytes <= 0:
        return ""

    remaining = max_bytes
    budgeted: list[tuple[Path, str]] = []
    for index in reversed(range(len(discovered))):
        path, content = discovered[index]
        annotation = f"<!-- From: {path} -->\n"
        separator = "\n\n" if index < len(discovered) - 1 else ""
        remaining -= len(annotation.encode("utf-8")) + len(separator.encode("utf-8"))
        if remaining <= 0:
            budgeted.append((path, ""))
            remaining = 0
            continue

        encoded = content.encode("utf-8")
        if len(encoded) > remaining:
            content = encoded[:remaining].decode("utf-8", errors="ignore").strip()
        remaining -= len(content.encode("utf-8"))
        budgeted.append((path, content))

    budgeted.reverse()
    parts = [
        f"<!-- From: {path} -->\n{content}"
        for path, content in budgeted
        if content
    ]
    return "\n\n".join(parts)
