"""Resolve monkeypatchable symbols through ``deepy.ui.classic.terminal`` at call time."""

from __future__ import annotations

from typing import Any


def resolve(name: str) -> Any:
    import deepy.ui.classic.terminal as terminal_module

    return getattr(terminal_module, name)
