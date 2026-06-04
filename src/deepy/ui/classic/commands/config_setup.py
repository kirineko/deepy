"""Interactive ``/reset`` config-setup flow for the Classic terminal UI.

Self-contained handlers for re-running the first-run configuration wizard from
within an interactive session. They render through the ``console`` argument and
read input via a directly-instantiated ``PromptSession`` (not the run loop's
patched ``prompt_for_input``), so they have no dependency on ``terminal.py``
internals and were extracted there to keep the run-loop module focused.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from deepy.config import (
    Settings,
    default_base_url_for_provider,
    default_model_for_provider,
    is_supported_model_for_provider,
    is_valid_thinking_mode_for_provider,
    provider_info_for,
    ui_setup_from_selection,
    ui_setup_number,
    write_config,
)
from deepy.ui.classic.commands.config_choices import _format_ui_interface_label, _print_ui_choices
from deepy.ui.classic.commands.model_commands import (
    _prompt_for_model_selection,
    _prompt_for_provider_selection,
    _prompt_for_reasoning_mode_selection,
)
from deepy.ui.shared.render.styles import UiPalette


def _handle_reset_command(
    console: Console,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    if settings.path is None:
        console.print(f"[{palette.error}]Cannot reset config: config path is unknown.[/]")
        return current_session_id
    previous_text = settings.path.read_text(encoding="utf-8") if settings.path.exists() else None
    if settings.path.exists():
        settings.path.unlink()
        console.print(f"Removed {settings.path}")
    else:
        console.print(f"No existing config at {settings.path}")
    console.print("Starting Deepy configuration setup...")
    try:
        interface, theme = _run_interactive_config_setup(settings.path, previous=settings, console=console)
    except (KeyboardInterrupt, EOFError, StopIteration):
        _restore_config_after_failed_setup(settings.path, previous_text)
        console.print(f"[{palette.warning}]{_setup_cancelled_message(previous_text)}[/]")
        return current_session_id
    console.print(f"Wrote {settings.path}")
    if interface != "classic" or theme != settings.ui.theme:
        console.print(
            f"[{palette.warning}]UI selection changed to "
            f"{_format_ui_interface_label(interface)} {theme}. "
            "Restart Deepy for the UI and theme selection to take effect.[/]"
        )
    return current_session_id


def _setup_cancelled_message(previous_text: str | None) -> str:
    if previous_text is None:
        return "Configuration setup cancelled. No config was written."
    return "Configuration setup cancelled. Existing config was left unchanged."


def _restore_config_after_failed_setup(config_path: Path, previous_text: str | None) -> None:
    if previous_text is None:
        try:
            config_path.unlink()
        except FileNotFoundError:
            pass
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(previous_text, encoding="utf-8")
    try:
        config_path.chmod(0o600)
    except OSError:
        pass


def _run_interactive_config_setup(
    config_path: Path,
    *,
    previous: Settings,
    console: Console,
) -> tuple[str, str]:
    provider = _prompt_for_provider_selection(
        previous.model.provider,
        console=console,
        input_func=lambda label: _prompt_config_value(label, default=""),
    ) or previous.model.provider
    provider_info = provider_info_for(provider)
    console.print(f"Provider: {provider}")
    if provider_info.api_key_url:
        console.print(f"Create an API key at {provider_info.api_key_url}")
    api_key = _prompt_config_value("API key", default="", is_password=True)
    model_default = (
        previous.model.name
        if previous.model.provider == provider and is_supported_model_for_provider(previous.model.name, provider)
        else default_model_for_provider(provider)
    )
    model = _prompt_for_model_selection(
        model_default,
        provider=provider,
        console=console,
        input_func=lambda label: _prompt_config_value(label, default=""),
        allow_custom_model=True,
    ) or model_default
    base_default = (
        previous.model.base_url
        if previous.model.provider == provider
        else default_base_url_for_provider(provider)
    )
    base_url = _prompt_config_value("Base URL", default=base_default)
    thinking_default = (
        previous.model.reasoning_mode
        if previous.model.provider == provider and is_valid_thinking_mode_for_provider(previous.model.reasoning_mode, provider)
        else provider_info_for(provider).default_thinking_mode
    )
    thinking_mode = _prompt_for_reasoning_mode_selection(
        thinking_default,
        provider=provider,
        console=console,
        input_func=lambda label: _prompt_config_value(label, default=""),
        setup_flow=True,
    ) or thinking_default
    interface, theme = _prompt_ui_config_choice(
        default_interface=previous.ui.interface,
        default_theme=previous.ui.theme,
        console=console,
    )
    write_config(
        config_path,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        thinking_mode=thinking_mode,
        theme=theme,
        interface=interface,
    )
    return interface, theme


def _prompt_ui_config_choice(
    *,
    default_interface: str,
    default_theme: str,
    console: Console,
) -> tuple[str, str]:
    _print_ui_choices(console)
    value = _prompt_config_value(
        "UI number",
        default=ui_setup_number(default_interface, default_theme),
    )
    return ui_setup_from_selection(
        value,
        default_interface=default_interface,
        default_theme=default_theme,
    )


def _prompt_config_value(label: str, *, default: str, is_password: bool = False) -> str:
    from prompt_toolkit import PromptSession

    prompt = f"{label}"
    if default and not is_password:
        prompt += f" [{default}]"
    prompt += ": "
    value = PromptSession().prompt(prompt, default="" if is_password else default, is_password=is_password)
    value = value.strip()
    return value or default
