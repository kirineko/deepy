"""Resolve monkeypatchable symbols through ``deepy.ui.modern.app`` at call time."""

from __future__ import annotations

from typing import Any


def resolve(name: str) -> Any:
    import deepy.ui.modern.app as app_module

    return getattr(app_module, name)
