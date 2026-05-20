from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from deepy.skills import SkillInfo
from deepy.update_check import VersionUpdate
from deepy.ui.styles import DARK_PALETTE, UiPalette
from deepy.ui.slash_commands import (
    BUILTIN_SLASH_COMMANDS,
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


CORE_WELCOME_COMMANDS = (
    "/resume",
    "/new",
    "/skills",
)

CORE_SHORTCUT_TIPS = (
    WelcomeTip("/", "Command menu"),
    WelcomeTip("Esc", "Interrupt turn"),
    WelcomeTip("Ctrl+D twice", "Quit"),
)

COMPACT_COMMAND_DESCRIPTIONS = {
    "/skills": "Manage skills",
    "/new": "New session",
    "/resume": "Resume session",
    "/exit": "Quit",
}

DEEPY_ASCII_LOGO = (
    "   .----.",
    "  | >_ |  o",
    "   '----'",
    "    Deepy",
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
    del skills
    slash_tips = [
        WelcomeTip(
            label=item.label,
            description=COMPACT_COMMAND_DESCRIPTIONS.get(
                item.label,
                format_slash_command_description(item.description),
            ),
        )
        for item in BUILTIN_SLASH_COMMANDS
        if item.label in CORE_WELCOME_COMMANDS
    ]
    return [*slash_tips, *CORE_SHORTCUT_TIPS]


def build_welcome_settings(
    *,
    provider: str = "deepseek",
    model: str,
    thinking_enabled: bool,
    reasoning_effort: str,
    thinking_mode: str | None = None,
    project_root: str | Path,
    current_version: str,
    version_update: VersionUpdate | None = None,
    home: str | Path | None = None,
    theme: str | None = None,
    resolved_theme: str | None = None,
) -> list[WelcomeSetting]:
    settings = [
        WelcomeSetting("Version", _format_version_value(current_version, version_update)),
        WelcomeSetting("Provider", provider),
        WelcomeSetting("Model", model),
        WelcomeSetting("Thinking", thinking_mode or (reasoning_effort if thinking_enabled else "none")),
        WelcomeSetting("CWD", format_home_relative_path(project_root, home=home)),
    ]
    if theme:
        value = theme if not resolved_theme or resolved_theme == theme else f"{theme} -> {resolved_theme}"
        settings.append(WelcomeSetting("Theme", value))
    if version_update is not None:
        settings.append(WelcomeSetting("Update", version_update.install_hint))
    return settings


def _format_version_value(current_version: str, version_update: VersionUpdate | None) -> str:
    if version_update is None:
        return current_version
    return (
        f"{current_version} -> {version_update.latest_version} available "
        f"from {version_update.source}"
    )


def build_deepy_ascii_logo(*, palette: UiPalette | None = None) -> Text:
    palette = palette or DARK_PALETTE
    logo = Text()
    for index, line in enumerate(DEEPY_ASCII_LOGO):
        if index:
            logo.append("\n")
        logo.append(line, style=f"bold {palette.accent}" if "Deepy" in line else palette.info)
    return logo


def _build_section(
    title: str,
    rows: Sequence[WelcomeSetting | WelcomeTip],
    *,
    palette: UiPalette,
) -> Table:
    section = Table.grid()
    section.add_column()
    section.add_row(Text(title, style=palette.markdown_bold))
    section.add_row(Text(""))

    body = Table.grid(padding=(0, 2))
    body.add_column(style=palette.accent, no_wrap=True)
    body.add_column(style=palette.markdown_bold)
    for row in rows:
        body.add_row(row.label, row.description if isinstance(row, WelcomeTip) else row.value)
    section.add_row(body)
    return section


def build_welcome_panel(
    *,
    provider: str = "deepseek",
    model: str,
    thinking_enabled: bool,
    reasoning_effort: str,
    thinking_mode: str | None = None,
    project_root: str | Path,
    skills: list[SkillInfo],
    current_version: str,
    version_update: VersionUpdate | None = None,
    home: str | Path | None = None,
    theme: str | None = None,
    resolved_theme: str | None = None,
    palette: UiPalette | None = None,
) -> Panel:
    palette = palette or DARK_PALETTE
    settings = build_welcome_settings(
        provider=provider,
        model=model,
        thinking_enabled=thinking_enabled,
        reasoning_effort=reasoning_effort,
        thinking_mode=thinking_mode,
        project_root=project_root,
        current_version=current_version,
        version_update=version_update,
        home=home,
        theme=theme,
        resolved_theme=resolved_theme,
    )
    tips = build_welcome_tips(skills)

    hero = Table.grid(padding=(0, 3), expand=False)
    hero.add_column()
    hero.add_column(ratio=1)

    intro = Text()
    intro.append("Deepy\n", style=f"bold {palette.assistant}")
    intro.append("Terminal coding agent for OpenAI-compatible models.\n", style=palette.markdown_bold)
    intro.append("Read, edit, run tools, and keep project context.", style=palette.muted)

    hero.add_row(build_deepy_ascii_logo(palette=palette), intro)

    body = Table.grid(padding=(0, 4), expand=False)
    body.add_column()
    body.add_column()
    body.add_row(
        _build_section("Session", settings, palette=palette),
        _build_section("Commands", tips[:10], palette=palette),
    )

    return Panel(
        Group(
            hero,
            Text(""),
            body,
        ),
        title="Deepy is ready",
        border_style=palette.panel_border,
        expand=False,
    )
