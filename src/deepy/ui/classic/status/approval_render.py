from __future__ import annotations

import io
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.panel import Panel

from deepy.audit import PendingApproval
from deepy.ui.shared.render.audit_approval_panel import build_approval_panel
from deepy.ui.shared.render.styles import UiPalette


def _approval_panel(
    item: PendingApproval,
    *,
    palette: UiPalette,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
) -> Panel:
    panel, _ = _approval_panel_state(
        item,
        palette=palette,
        project_root=project_root,
        expanded=expanded,
        width=width,
    )
    return panel


def _approval_panel_ansi(
    item: PendingApproval,
    *,
    palette: UiPalette,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
    color_system: Literal["auto", "standard", "256", "truecolor", "windows"] | None = "truecolor",
) -> str:
    buffer = io.StringIO()
    render_console = Console(
        file=buffer,
        force_terminal=True,
        color_system=color_system,
        width=width,
    )
    render_console.print(
        _approval_panel(
            item,
            palette=palette,
            project_root=project_root,
            expanded=expanded,
            width=width,
        )
    )
    return buffer.getvalue().rstrip("\n")


def _approval_panel_state(
    item: PendingApproval,
    *,
    palette: UiPalette,
    project_root: str | Path | None = None,
    expanded: bool = False,
    width: int | None = None,
) -> tuple[Panel, bool]:
    return build_approval_panel(
        item,
        palette=palette,
        project_root=project_root,
        expanded=expanded,
        width=width,
    )
