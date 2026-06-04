from __future__ import annotations

from rich.console import Console

from deepy.config import (
    PROVIDER_CATALOG,
    UI_THEMES,
    allows_custom_model_for_provider,
    is_supported_model_for_provider,
    is_supported_provider,
    is_valid_thinking_mode_for_provider,
    provider_info_for,
)
from deepy.ui.shared.model_picker import thinking_mode_choices
from deepy.ui.shared.render.styles import UiPalette
from deepy.ui.classic.pickers.theme_picker import THEME_CHOICES


def _format_view_mode_confirmation(view_mode: str) -> str:
    reasoning_state = "reasoning shown" if view_mode == "full" else "reasoning hidden"
    return f"View: {view_mode} · {reasoning_state}"


def _print_model_choices(console: Console) -> None:
    console.print("Available providers and models:")
    for provider in PROVIDER_CATALOG:
        console.print(f"{provider.id} - {provider.description}")
        for index, model in enumerate(provider.models, 1):
            console.print(f"  {index}. {model.name} - {model.description}")
        modes = ", ".join(provider.thinking_modes)
        console.print(f"  thinking: {modes}")


def _print_model_usage(console: Console, palette: UiPalette) -> None:
    console.print(
        f"[{palette.error}]Usage:[/] /model | /model list | "
        "/model set deepseek-v4-pro|deepseek-v4-flash [none|high|max] | "
        "/model set openrouter xiaomi/mimo-v2.5-pro none|minimal|low|medium|high|xhigh | "
        "/model set xiaomi mimo-v2.5-pro enabled|disabled | "
        "/model provider deepseek|openrouter|xiaomi | "
        "/model thinking <mode>"
    )


def _openrouter_thinking_state_from_selection(value: str, *, default: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"1", "enabled", "enable", "on", "true", "yes"}:
        return "enabled"
    if normalized in {"2", "disabled", "disable", "off", "false", "no", "none"}:
        return "disabled"
    return default


def _openrouter_effort_from_selection(value: str, *, default: str) -> str:
    normalized = value.strip().lower()
    by_number = {
        "1": "enabled",
        "2": "xhigh",
        "3": "high",
        "4": "medium",
        "5": "low",
        "6": "minimal",
    }
    if normalized in by_number:
        return by_number[normalized]
    if normalized in {"default", "enabled"}:
        return "enabled"
    if normalized in {"xhigh", "high", "medium", "low", "minimal"}:
        return normalized
    return default if default in {"enabled", "xhigh", "high", "medium", "low", "minimal"} else "enabled"


def _provider_from_selection(value: str) -> str | None:
    normalized = value.strip().lower()
    by_number = {str(index): provider.id for index, provider in enumerate(PROVIDER_CATALOG, 1)}
    if normalized in by_number:
        return by_number[normalized]
    return normalized if is_supported_provider(normalized) else None


def _model_from_selection(value: str, *, provider: str, allow_custom_model: bool = False) -> str | None:
    normalized = value.strip()
    by_number = {str(index): model.name for index, model in enumerate(provider_info_for(provider).models, 1)}
    if normalized in by_number:
        return by_number[normalized]
    if allow_custom_model and allows_custom_model_for_provider(provider) and normalized:
        return normalized
    return normalized if is_supported_model_for_provider(normalized, provider) else None


def _reasoning_mode_from_selection(value: str, *, provider: str) -> str | None:
    normalized = value.strip().lower()
    choices = thinking_mode_choices(provider)
    by_number = {str(index): mode for index, (mode, _label) in enumerate(choices, 1)}
    if normalized in by_number:
        return by_number[normalized]
    return normalized if is_valid_thinking_mode_for_provider(normalized, provider) else None


def _print_provider_choices(console: Console) -> None:
    console.print("Providers:")
    for index, provider in enumerate(PROVIDER_CATALOG, 1):
        console.print(f"{index}. {provider.id} - {provider.description}")


def _print_provider_model_choices(console: Console, provider: str) -> None:
    console.print(f"Models for {provider}:")
    for index, model in enumerate(provider_info_for(provider).models, 1):
        console.print(f"{index}. {model.name} - {model.description}")


def _print_reasoning_choices(console: Console, provider: str = "deepseek") -> None:
    console.print("Thinking:")
    for index, (value, label) in enumerate(thinking_mode_choices(provider), 1):
        console.print(f"{index}. {label}")


def _print_theme_choices(console: Console) -> None:
    console.print("Available themes:")
    for index, (_theme, label) in enumerate(THEME_CHOICES, 1):
        console.print(f"{index}. {label}")


def _print_ui_choices(console: Console) -> None:
    console.print("Available UI modes:")
    console.print("1. Classic UI + dark theme  Default terminal UI")
    console.print("2. Classic UI + light theme")
    console.print("3. Modern UI + dark theme   Textual UI")
    console.print("4. Modern UI + light theme  Textual UI")


def _format_ui_interface_label(interface: str) -> str:
    return "Modern UI" if interface == "modern" else "Classic UI"


def _theme_from_selection(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in UI_THEMES:
        return normalized
    return {"1": "dark", "2": "light"}.get(normalized)
