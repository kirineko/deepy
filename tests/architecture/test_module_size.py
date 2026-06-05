"""Regression guard: tracked source modules must stay under the size ceiling."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "deepy"

# Baseline at change start (2026-06-05); target is strictly below MODULE_SIZE_CEILING.
MODULE_SIZE_CEILING = 800
TRACKED_MODULES: dict[str, int] = {
    "tools/builtin.py": 3846,
    "ui/classic/terminal.py": 2697,
    "ui/modern/app.py": 2632,
    "tools/agents.py": 1079,
    "config/settings.py": 1070,
    "llm/runner.py": 943,
}


def _line_count(relative_path: str) -> int:
    path = SRC_ROOT / relative_path
    if not path.is_file():
        pytest.fail(f"Tracked module missing: {relative_path} (expected at {path})")
    return len(path.read_text(encoding="utf-8").splitlines())


@pytest.mark.parametrize("relative_path", sorted(TRACKED_MODULES))
def test_tracked_module_under_size_ceiling(relative_path: str) -> None:
    count = _line_count(relative_path)
    baseline = TRACKED_MODULES[relative_path]
    if count >= MODULE_SIZE_CEILING:
        pytest.fail(
            f"{relative_path} has {count} lines (baseline {baseline}); "
            f"must stay under {MODULE_SIZE_CEILING}"
        )
