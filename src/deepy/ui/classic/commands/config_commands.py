"""Theme / UI / view / input-suggestion slash commands for the Classic UI.

Self-contained config-mutation handlers. Each renders through the ``console``
argument, resolves interactive choices via the model-command prompts, and
persists through the ``deepy.config`` writers, so they have no dependency on
``terminal.py`` internals beyond the ``InputFunc``/``SlashCommand`` type aliases
(imported only for type checking).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from deepy.config import (
    UI_THEMES,
    Settings,
    update_config_input_suggestions_enabled,
    update_config_theme,
    update_config_ui_interface,
    update_config_view_mode,
)
from deepy.ui.classic.commands.config_choices import _format_ui_interface_label, _format_view_mode_confirmation
from deepy.ui.classic.commands.model_commands import _prompt_for_theme_selection, _prompt_for_ui_selection
from deepy.ui.shared.render.styles import UiPalette

if TYPE_CHECKING:
    from deepy.ui.shared.input.commands import SlashCommand
    from deepy.ui.classic.terminal import InputFunc


def _handle_theme_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    theme = command.argument
    if not theme:
        console.print(f"Current theme: {settings.ui.theme}")
        selected = _prompt_for_theme_selection(
            settings.ui.theme,
            console=console,
            input_func=input_func,
        )
        if selected is None:
            console.print("Theme unchanged.")
            return current_session_id
        theme = selected
    if theme not in UI_THEMES:
        console.print(f"[{palette.error}]Usage:[/] /theme dark|light")
        return current_session_id
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist theme: config path is unknown.[/]")
        return current_session_id
    update_config_theme(settings.path, theme)
    console.print(f"Saved UI theme: {theme}")
    console.print("Restart Deepy to apply the theme everywhere.")
    return current_session_id


def _handle_ui_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    interface = command.argument.strip().lower()
    if not interface:
        console.print(f"Current UI: {settings.ui.interface}")
        selected = _prompt_for_ui_selection(
            settings.ui.interface,
            console=console,
            input_func=input_func,
        )
        if selected is None:
            console.print("UI unchanged.")
            return current_session_id
        interface = selected
    if interface not in {"classic", "modern"}:
        console.print(f"[{palette.error}]Usage:[/] /ui classic|modern")
        return current_session_id
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist UI: config path is unknown.[/]")
        return current_session_id
    update_config_ui_interface(settings.path, interface)
    console.print(f"Saved UI: {_format_ui_interface_label(interface)}")
    console.print("Restart Deepy to enter the selected UI.")
    return current_session_id


def _handle_input_suggestion_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    if command.argument.strip():
        console.print(f"[{palette.error}]Usage:[/] /input-suggestion")
        return current_session_id
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist input suggestion setting: config path is unknown.[/]")
        return current_session_id
    enabled = not settings.ui.input_suggestions_enabled
    update_config_input_suggestions_enabled(settings.path, enabled)
    console.print(f"Input suggestions {'enabled' if enabled else 'disabled'}.")
    return current_session_id


def _handle_view_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    argument = command.argument.strip().lower()
    current = settings.ui.view_mode
    if not argument or argument == "toggle":
        selected = "full" if current == "concise" else "concise"
    elif argument in {"concise", "full"}:
        selected = argument
    else:
        console.print(f"[{palette.error}]Usage:[/] /view \\[toggle|concise|full]")
        return current_session_id
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist view mode: config path is unknown.[/]")
        return current_session_id
    update_config_view_mode(settings.path, selected)
    console.print(_format_view_mode_confirmation(selected))
    return current_session_id
