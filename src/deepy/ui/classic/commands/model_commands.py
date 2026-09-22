"""Model / provider / theme / UI selection handlers for the Classic terminal UI.

Self-contained slash-command handlers and interactive prompts. They render via
the ``console`` argument and resolve choices through ``config_choices`` and the
picker entry points, with no dependency on ``terminal.py`` internals beyond the
``InputFunc``/``SlashCommand`` type aliases (imported only for type checking).
"""

from __future__ import annotations

from deepy.config.retired_models import retired_model_guidance

from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt

from deepy.config import (
    Settings,
    is_supported_model_for_provider,
    is_supported_provider,
    is_valid_thinking_mode_for_provider,
    load_settings,
    ui_interface_from_selection,
    ui_interface_number,
    update_config_model_settings,
)
from deepy.ui.classic.commands.config_choices import (
    _model_from_selection,
    _print_model_choices,
    _print_model_usage,
    _print_provider_choices,
    _print_provider_model_choices,
    _print_reasoning_choices,
    _print_theme_choices,
    _provider_from_selection,
    _reasoning_mode_from_selection,
    _theme_from_selection,
)
from deepy.ui.shared.model_picker import (
    pick_model,
    pick_provider,
    pick_reasoning_mode,
    provider_api_key_reconfiguration_message,
)
from deepy.ui.shared.render.styles import UiPalette
from deepy.ui.classic.pickers.theme_picker import pick_theme

if TYPE_CHECKING:
    from deepy.ui.shared.input.commands import SlashCommand
    from deepy.ui.classic.terminal import InputFunc


def _handle_model_command(
    command: SlashCommand,
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    parts = command.argument.split()
    if not parts:
        return _handle_interactive_model_selection(
            console,
            current_session_id,
            settings,
            palette,
            input_func=input_func,
        )
    action = parts[0].lower()
    if action == "list" and len(parts) == 1:
        _print_model_choices(console)
        return current_session_id
    if action == "provider" and len(parts) == 2:
        provider = parts[1].lower()
        if not is_supported_provider(provider):
            console.print(f"[{palette.error}]Invalid provider:[/] {provider}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            provider=provider,
        )
    if action == "set" and len(parts) in {2, 3}:
        model = parts[1]
        provider = "deepseek"
        if not is_supported_model_for_provider(model, provider):
            console.print(retired_model_guidance(provider, model) or f"Invalid model: {model}", style=palette.error)
            _print_model_usage(console, palette)
            return current_session_id
        reasoning_mode = parts[2] if len(parts) == 3 else None
        if reasoning_mode is not None and not is_valid_thinking_mode_for_provider(reasoning_mode, provider):
            console.print(f"[{palette.error}]Invalid thinking mode:[/] {reasoning_mode}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            provider=provider,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    if action == "set" and len(parts) == 4:
        provider = parts[1].lower()
        model = parts[2]
        reasoning_mode = parts[3].lower()
        if not is_supported_provider(provider):
            console.print(f"[{palette.error}]Invalid provider:[/] {provider}")
            _print_model_usage(console, palette)
            return current_session_id
        if not is_supported_model_for_provider(model, provider):
            console.print(retired_model_guidance(provider, model) or f"Invalid model: {model}", style=palette.error)
            _print_model_usage(console, palette)
            return current_session_id
        if not is_valid_thinking_mode_for_provider(reasoning_mode, provider):
            console.print(f"[{palette.error}]Invalid thinking mode:[/] {reasoning_mode}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            provider=provider,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    if action in {"reasoning", "thinking"} and len(parts) == 2:
        reasoning_mode = parts[1]
        provider = settings.model.provider
        if not is_valid_thinking_mode_for_provider(reasoning_mode, provider):
            console.print(f"[{palette.error}]Invalid thinking mode:[/] {reasoning_mode}")
            _print_model_usage(console, palette)
            return current_session_id
        return _save_model_settings(
            console,
            current_session_id,
            settings,
            palette,
            reasoning_mode=reasoning_mode,
        )
    _print_model_usage(console, palette)
    return current_session_id


def _handle_interactive_model_selection(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    input_func: InputFunc | None = None,
) -> str | None:
    console.print(
        f"Current provider: {settings.model.provider} · model: {settings.model.name} · "
        f"thinking: {settings.model.reasoning_mode}"
    )
    selected_provider = _prompt_for_provider_selection(
        settings.model.provider,
        console=console,
        input_func=input_func,
    )
    if selected_provider is None:
        console.print("Model unchanged.")
        return current_session_id
    selected_model = _prompt_for_model_selection(
        settings.model_for_provider(selected_provider).name,
        provider=selected_provider,
        console=console,
        input_func=input_func,
    )
    if selected_model is None:
        console.print("Model unchanged.")
        return current_session_id
    selected_reasoning = _prompt_for_reasoning_mode_selection(
        settings.model_for_provider(selected_provider).reasoning_mode,
        provider=selected_provider,
        console=console,
        input_func=input_func,
    )
    if selected_reasoning is None:
        console.print("Model unchanged.")
        return current_session_id
    return _save_model_settings(
        console,
        current_session_id,
        settings,
        palette,
        provider=selected_provider,
        model=selected_model,
        reasoning_mode=selected_reasoning,
    )


def _save_model_settings(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
    *,
    provider: str | None = None,
    model: str | None = None,
    reasoning_mode: str | None = None,
) -> str | None:
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot persist model settings: config path is unknown.[/]")
        return current_session_id
    try:
        update_config_model_settings(
            settings.path,
            provider=provider,
            model=model,
            reasoning_mode=reasoning_mode,
        )
    except (ValueError, OSError) as exc:
        console.print(f"[{palette.error}]{exc}[/]")
        return current_session_id
    saved_settings = load_settings(settings.path)
    console.print(
        f"Saved provider: {saved_settings.model.provider} · "
        f"model: {saved_settings.model.name} · "
        f"thinking: {saved_settings.model.reasoning_mode}"
    )
    if not saved_settings.model.api_key:
        console.print(provider_api_key_reconfiguration_message(saved_settings.model.provider))
    return current_session_id


def _prompt_for_provider_selection(
    default: str,
    *,
    console: Console,
    input_func: InputFunc | None = None,
) -> str | None:
    if input_func is None:
        return pick_provider(default)
    _print_provider_choices(console)
    value = input_func("Provider number or name").strip()
    if not value:
        return None
    return _provider_from_selection(value)


def _prompt_for_model_selection(
    default: str,
    *,
    provider: str,
    console: Console,
    input_func: InputFunc | None = None,
    allow_custom_model: bool = False,
) -> str | None:
    if input_func is None:
        return pick_model(default, provider=provider)
    _print_provider_model_choices(console, provider)
    value = input_func("Model number or name").strip()
    if not value:
        return None
    return _model_from_selection(value, provider=provider, allow_custom_model=allow_custom_model)


def _prompt_for_reasoning_mode_selection(
    default: str,
    *,
    provider: str,
    console: Console,
    input_func: InputFunc | None = None,
    setup_flow: bool = False,
) -> str | None:
    if input_func is None:
        return pick_reasoning_mode(default, provider=provider)
    _print_reasoning_choices(console, provider)
    value = input_func("Thinking number or name").strip()
    if not value:
        return None
    return _reasoning_mode_from_selection(value, provider=provider)


def _prompt_for_ui_selection(
    default: str,
    *,
    console: Console,
    input_func: InputFunc | None = None,
) -> str | None:
    if input_func is None:
        console.print("Available UIs:")
        console.print("1. Classic UI")
        console.print("2. Modern UI")
        value = Prompt.ask("UI number or name", default=ui_interface_number(default))
    else:
        console.print("Available UIs:")
        console.print("1. Classic UI")
        console.print("2. Modern UI")
        value = input_func("UI number or name").strip()
    if not value:
        return None
    return ui_interface_from_selection(value, default=default)


def _prompt_for_theme_selection(
    default: str,
    *,
    console: Console,
    input_func: InputFunc | None = None,
) -> str | None:
    if input_func is None:
        return pick_theme(default)
    _print_theme_choices(console)
    value = input_func("Theme number or name").strip()
    if not value:
        return None
    return _theme_from_selection(value)
