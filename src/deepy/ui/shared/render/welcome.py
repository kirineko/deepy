from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from deepy.skills import SkillInfo
from deepy.ui.shared.input.slash_commands import (
    BUILTIN_SLASH_COMMANDS,
    format_slash_command_description,
)
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette
from deepy.update_check import VersionUpdate


@dataclass(frozen=True)
class WelcomeTip:
    label: str
    description: str


@dataclass(frozen=True)
class WelcomeSetting:
    label: str
    value: str


CORE_WELCOME_COMMANDS = (
    "/help",
    "/new",
    "/resume",
    "/model",
    "/skills",
    "/status",
)

CORE_SHORTCUT_TIPS = (
    WelcomeTip("/", "Command menu"),
    WelcomeTip("Esc", "Interrupt turn"),
    WelcomeTip("Ctrl+D twice", "Quit"),
)

COMPACT_COMMAND_DESCRIPTIONS = {
    "/help": "Show commands and shortcuts",
    "/model": "Change provider or model",
    "/new": "Start a fresh session",
    "/resume": "Continue previous session",
    "/skills": "Install and manage skills",
    "/status": "Show usage and context",
    "/exit": "Quit",
}

DEEPY_ASCII_LOGO = (
    "    .--------",
    "   /  >_ o /|  ",
    "  /_______/ |",
    "  |       | /",
    "   '------'",
    "     Deepy",
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
    slash_by_label = {item.label: item for item in BUILTIN_SLASH_COMMANDS}
    slash_tips = []
    for label in CORE_WELCOME_COMMANDS:
        item = slash_by_label.get(label)
        if item is None:
            continue
        slash_tips.append(
            WelcomeTip(
                label=item.label,
                description=COMPACT_COMMAND_DESCRIPTIONS.get(
                    item.label,
                    format_slash_command_description(item.description),
                ),
            )
        )
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
        WelcomeSetting(
            "Thinking", thinking_mode or (reasoning_effort if thinking_enabled else "none")
        ),
        WelcomeSetting("CWD", format_home_relative_path(project_root, home=home)),
    ]
    if theme:
        value = (
            theme
            if not resolved_theme or resolved_theme == theme
            else f"{theme} -> {resolved_theme}"
        )
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


def _build_welcome_brand(*, palette: UiPalette) -> Table:
    intro = Text()
    intro.append("\n")
    intro.append("Welcome to Deepy\n", style=f"bold {palette.accent}")
    intro.append(
        "Terminal coding agent for DeepSeek\n",
        style=palette.markdown_bold,
    )
    intro.append("Read, edit, run tools, and keep context.", style=palette.muted)

    brand = Table.grid(padding=(0, 2), expand=True)
    brand.add_column(no_wrap=True)
    brand.add_column(ratio=1)
    brand.add_row(Text(""), Text(""))
    brand.add_row(build_deepy_ascii_logo(palette=palette), intro)
    return brand


def _build_welcome_info(settings: Sequence[WelcomeSetting], *, palette: UiPalette) -> Text:
    info = Text()
    info.append("Session\n\n", style=f"bold {palette.markdown_bold}")
    for line in _compact_setting_lines(settings):
        info.append(line.label, style=palette.accent)
        info.append(f" {line.value}\n", style=palette.markdown_bold)
    if info.plain.endswith("\n"):
        info.rstrip()
    return info


def _compact_setting_lines(settings: Sequence[WelcomeSetting]) -> list[WelcomeSetting]:
    by_label = {item.label: item.value for item in settings}
    lines: list[WelcomeSetting] = []
    provider = by_label.get("Provider")
    if provider:
        lines.append(WelcomeSetting("Provider", provider))
    model = by_label.get("Model")
    thinking = by_label.get("Thinking")
    if model:
        lines.append(WelcomeSetting("Model", model))
    if thinking:
        lines.append(WelcomeSetting("Reasoning", _format_reasoning_value(thinking)))
    if cwd := by_label.get("CWD"):
        lines.append(WelcomeSetting("CWD", _compact_welcome_value(cwd, max_chars=22)))
    if theme := by_label.get("Theme"):
        lines.append(WelcomeSetting("Theme", theme))
    if version := by_label.get("Version"):
        lines.append(WelcomeSetting("Version", version))
    if update := by_label.get("Update"):
        lines.append(WelcomeSetting("Update", update))
    return lines


def _compact_welcome_value(value: str, *, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[: max(0, max_chars - 3)]}..."


def _format_reasoning_value(thinking: str) -> str:
    if thinking == "none":
        return "disabled"
    if thinking in {"enabled", "disabled"}:
        return thinking
    return f"enabled · effort {thinking}"


def _build_welcome_commands(tips: Sequence[WelcomeTip], *, palette: UiPalette) -> Text:
    commands = [tip for tip in tips if tip.label in CORE_WELCOME_COMMANDS]
    text = Text()
    text.append("Commands\n\n", style=f"bold {palette.markdown_bold}")
    label_width = max((len(tip.label) for tip in commands), default=0)
    for index, tip in enumerate(commands):
        if index:
            text.append("\n")
        text.append(tip.label.ljust(label_width), style=f"bold {palette.accent}")
        text.append(f"  {tip.description}", style=palette.markdown_bold)
    return text


def _build_welcome_sections(
    settings: Sequence[WelcomeSetting],
    tips: Sequence[WelcomeTip],
    *,
    palette: UiPalette,
) -> Table:
    sections = Table.grid(padding=(0, 3), expand=True)
    sections.add_column(ratio=6)
    sections.add_column(ratio=8)
    sections.add_row(
        _build_welcome_info(settings, palette=palette),
        _build_welcome_commands(tips, palette=palette),
    )
    return sections


def _build_welcome_main(
    settings: Sequence[WelcomeSetting],
    tips: Sequence[WelcomeTip],
    *,
    palette: UiPalette,
) -> Table:
    main = Table.grid(padding=(0, 3), expand=True)
    main.add_column(ratio=3)
    main.add_column(no_wrap=True)
    main.add_column(ratio=5)
    main.add_row(
        _build_welcome_brand(palette=palette),
        _welcome_divider(palette=palette),
        _build_welcome_sections(settings, tips, palette=palette),
    )
    return main


def _welcome_divider(*, palette: UiPalette) -> Text:
    return Text("\n".join("│" for _ in range(8)), style=palette.panel_border)


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

    body = _build_welcome_main(settings, tips[:10], palette=palette)

    return Panel(
        body,
        title="Deepy",
        title_align="left",
        border_style=palette.panel_border,
        padding=(0, 1),
        expand=True,
    )
