from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from deepy.skills import SkillInfo
from deepy.ui.styles import STYLE_ACCENT, STYLE_INFO, STYLE_MUTED
from deepy.ui.slash_commands import (
    BUILTIN_SLASH_COMMANDS,
    build_slash_commands,
    format_slash_command_description,
)


@dataclass(frozen=True)
class WelcomeTip:
    label: str
    description: str


@dataclass(frozen=True)
class WelcomeSetting:
    label: str
    value: str


SHORTCUT_TIPS = (
    WelcomeTip("Enter", "Send the prompt"),
    WelcomeTip("Shift+Enter", "Insert a newline"),
    WelcomeTip("Esc", "Interrupt the current model turn"),
    WelcomeTip("/", "Open the skills and commands menu"),
    WelcomeTip("Ctrl+D twice", "Quit Deepy"),
)


def format_home_relative_path(value: str | Path, home: str | Path | None = None) -> str:
    path = Path(os.path.abspath(os.path.expanduser(str(value))))
    home_value = str(Path.home()) if home is None else str(home)
    home_path = Path(os.path.abspath(os.path.expanduser(home_value)))
    try:
        relative = path.relative_to(home_path)
    except ValueError:
        return str(path)
    return "~" if str(relative) == "." else f"~/{relative}"


def build_welcome_tips(skills: list[SkillInfo]) -> list[WelcomeTip]:
    slash_tips = [
        WelcomeTip(
            label=item.label,
            description=format_slash_command_description(item.description),
        )
        for item in build_slash_commands(skills)
        if item.kind != "skill" or bool(item.skill and item.skill.is_loaded)
    ]
    builtin_labels = {command.label for command in BUILTIN_SLASH_COMMANDS}
    shortcut_tips = [tip for tip in SHORTCUT_TIPS if tip.label not in builtin_labels]
    return [*slash_tips, *shortcut_tips]


def build_welcome_settings(
    *,
    model: str,
    thinking_enabled: bool,
    reasoning_effort: str,
    project_root: str | Path,
    home: str | Path | None = None,
) -> list[WelcomeSetting]:
    return [
        WelcomeSetting("Model", model),
        WelcomeSetting("Thinking Enabled", str(thinking_enabled)),
        WelcomeSetting("Reasoning Effort", reasoning_effort),
        WelcomeSetting("CWD", format_home_relative_path(project_root, home=home)),
    ]


def build_welcome_panel(
    *,
    model: str,
    thinking_enabled: bool,
    reasoning_effort: str,
    project_root: str | Path,
    skills: list[SkillInfo],
    home: str | Path | None = None,
) -> Panel:
    settings = build_welcome_settings(
        model=model,
        thinking_enabled=thinking_enabled,
        reasoning_effort=reasoning_effort,
        project_root=project_root,
        home=home,
    )
    tips = build_welcome_tips(skills)
    settings_table = Table.grid(padding=(0, 2))
    settings_table.add_column(style="bold")
    settings_table.add_column(style="bright_white")
    for item in settings:
        settings_table.add_row(item.label, item.value)

    tips_table = Table.grid(padding=(0, 2))
    tips_table.add_column(style=STYLE_ACCENT)
    tips_table.add_column()
    for tip in tips[:10]:
        tips_table.add_row(tip.label, tip.description)

    return Panel(
        Group(
            Text("Vibe coding for DeepSeek models in your terminal.", style=STYLE_MUTED),
            Text(""),
            settings_table,
            Text(""),
            Text("Shortcuts and commands", style="bold"),
            tips_table,
        ),
        title="Deepy",
        border_style=STYLE_INFO,
        expand=False,
    )
