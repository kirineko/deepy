from __future__ import annotations

import os
import tomllib
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import tomli_w

from deepy.audit import AuditMode, is_valid_audit_mode

from .providers import (
    DEFAULT_PROVIDER,
    DEFAULT_UI_INTERFACE,
    DEFAULT_UI_THEME,
    REASONING_MODES,
    SUPPORTED_DEEPSEEK_MODELS,
    THINKING_MODES,
    UI_INTERFACES,
    UI_INTERFACE_OPTIONS,
    UI_SETUP_OPTIONS,
    UI_THEME_OPTIONS,
    UI_THEMES,
    UI_VIEW_MODES,
    default_config_path,
    is_supported_model_for_provider,
    is_supported_provider,
    is_valid_config_model_for_provider,
    is_valid_thinking_mode_for_provider,
    mask_secret,
    provider_info_for,
)
from .schema import (
    ModelConfig,
    Settings,
)


def load_settings(
    path: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Settings:
    config_path = Path(path).expanduser() if path is not None else default_config_path()
    if config_path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    env = os.environ if env is None else env
    if not config_path.exists():
        return Settings.from_mapping({}, path=config_path, env=env)

    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)
    return Settings.from_mapping(raw, path=config_path, env=env)


def settings_to_toml_dict(settings: Settings, *, reveal_secret: bool = False) -> dict[str, Any]:
    data = _drop_empty(asdict(settings))
    data.pop("path", None)
    data.pop("provider_keys", None)
    data.pop("profiles", None)
    data.pop("model", None)
    data["config_version"] = 2
    data["active_provider"] = settings.model.provider
    data["providers"] = {key: dict(value) for key, value in settings.profiles.items()}
    for profile in data["providers"].values():
        if profile.get("api_key") and not reveal_secret:
            profile["api_key"] = mask_secret(profile["api_key"])
    data["context"].pop("explicit_window_tokens", None)
    data["context"].pop("window_is_resolved", None)
    data["resolved_model_limits"] = settings.model_limits.to_dict()
    if "ui" in data:
        data["ui"].pop("theme_configured", None)
    if "audit" in data:
        data["audit"].pop("invalid_mode", None)
        if "mode" in data["audit"] and isinstance(settings.audit.mode, AuditMode):
            data["audit"]["mode"] = settings.audit.mode.value
        if "mcp_safe_tools" in data["audit"]:
            data["audit"]["mcp_safe_tools"] = [
                {"server": item.server, "tool": item.tool} for item in settings.audit.mcp_safe_tools
            ]
    return _drop_empty(data)


def is_valid_ui_theme(value: str) -> bool:
    return value in UI_THEMES


def is_valid_ui_interface(value: str) -> bool:
    return value in UI_INTERFACES


def is_valid_ui_view_mode(value: str) -> bool:
    return value in UI_VIEW_MODES


def is_valid_config_audit_mode(value: str) -> bool:
    return is_valid_audit_mode(value)


def is_supported_deepseek_model(value: str) -> bool:
    return value in SUPPORTED_DEEPSEEK_MODELS


def is_supported_model(value: str, provider: str) -> bool:
    return is_supported_model_for_provider(value, provider)


def is_valid_reasoning_mode(value: str) -> bool:
    return value in REASONING_MODES


def is_valid_thinking_mode(value: str) -> bool:
    return value in THINKING_MODES


def ui_theme_number(theme: str) -> str:
    for number, value in UI_THEME_OPTIONS:
        if value == theme:
            return number
    return "1"


def ui_theme_from_selection(value: str, *, default: str = DEFAULT_UI_THEME) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return default if is_valid_ui_theme(default) else DEFAULT_UI_THEME
    if normalized in UI_THEMES:
        return normalized
    by_number = dict(UI_THEME_OPTIONS)
    selected = by_number.get(normalized)
    if selected is not None:
        return selected
    return default if is_valid_ui_theme(default) else DEFAULT_UI_THEME


def ui_interface_number(interface: str) -> str:
    for number, value in UI_INTERFACE_OPTIONS:
        if value == interface:
            return number
    return "1"


def ui_interface_from_selection(value: str, *, default: str = DEFAULT_UI_INTERFACE) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return default if is_valid_ui_interface(default) else DEFAULT_UI_INTERFACE
    if normalized in UI_INTERFACES:
        return normalized
    by_number = dict(UI_INTERFACE_OPTIONS)
    selected = by_number.get(normalized)
    if selected is not None:
        return selected
    return default if is_valid_ui_interface(default) else DEFAULT_UI_INTERFACE


def ui_setup_number(interface: str, theme: str) -> str:
    for number, option_interface, option_theme in UI_SETUP_OPTIONS:
        if option_interface == interface and option_theme == theme:
            return number
    return "1"


def ui_setup_from_selection(
    value: str,
    *,
    default_interface: str = DEFAULT_UI_INTERFACE,
    default_theme: str = DEFAULT_UI_THEME,
) -> tuple[str, str]:
    normalized = value.strip().lower()
    fallback = (
        default_interface if is_valid_ui_interface(default_interface) else DEFAULT_UI_INTERFACE,
        default_theme if is_valid_ui_theme(default_theme) else DEFAULT_UI_THEME,
    )
    if not normalized:
        return fallback
    for number, option_interface, option_theme in UI_SETUP_OPTIONS:
        if normalized in {
            number,
            f"{option_interface}-{option_theme}",
            f"{option_interface} {option_theme}",
        }:
            return option_interface, option_theme
    return fallback


def write_config(
    config_path: Path,
    *,
    api_key: str,
    provider: str = DEFAULT_PROVIDER,
    model: str,
    base_url: str | None = None,
    theme: str,
    interface: str = DEFAULT_UI_INTERFACE,
    thinking_mode: str | None = None,
) -> None:
    if not is_valid_ui_theme(theme):
        raise ValueError("UI theme must be one of: dark, light.")
    if not is_valid_ui_interface(interface):
        raise ValueError("UI interface must be one of: classic, modern.")
    if not is_supported_provider(provider):
        raise ValueError("Provider must be one of: deepseek, mimo, kimi, cli_proxy.")
    provider_info = provider_info_for(provider)
    if not is_valid_config_model_for_provider(model, provider):
        raise ValueError(
            "Model must be one of: "
            + ", ".join(model_info.name for model_info in provider_info.models)
        )
    mode = thinking_mode or provider_info.default_thinking_mode
    if not is_valid_thinking_mode_for_provider(mode, provider):
        raise ValueError("Thinking mode must be one of: " + ", ".join(provider_info.thinking_modes))
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    from .profiles import KEY_ENVIRONMENTS

    raw = _read_toml_mapping(path)
    # Explicit setup may replace a legacy format, but ordinary v2 setup is a merge.
    if "model" in raw or raw.get("config_version", 2) != 2:
        raw.pop("model", None)
        raw.pop("providers", None)
    profiles = dict(raw.get("providers", {}))
    profile = dict(profiles.get(provider, {}))
    profile.update(model=model, reasoning=mode)
    profile["base_url"] = base_url or profile.get("base_url") or provider_info.default_base_url
    profile.setdefault("api_key_env", KEY_ENVIRONMENTS[provider])
    if api_key.strip():
        profile["api_key"] = api_key.strip()
    profiles[provider] = profile
    raw.update(config_version=2, active_provider=provider, providers=profiles)
    ui = dict(raw.get("ui", {}))
    ui.update(theme=theme, interface=interface)
    raw["ui"] = ui
    _write_private_toml(path, raw)


def update_config_model_settings(
    config_path: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    reasoning_mode: str | None = None,
) -> None:
    from .profiles import parse_profiles

    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files.")
    raw = _read_toml_mapping(path)
    profiles, active = parse_profiles(raw)
    target = provider or active
    provider_info_for(target)
    profile = dict(profiles.get(target, {}))
    if model is not None:
        profile["model"] = model
    if base_url is not None:
        profile["base_url"] = base_url
    if reasoning_mode is not None:
        profile["reasoning"] = reasoning_mode
    current = ModelConfig.from_mapping({**profile, "provider": target})
    profile.setdefault("model", current.name)
    profile.setdefault("base_url", current.base_url)
    profile.setdefault("reasoning", current.reasoning_mode)
    profiles[target] = profile
    raw.update(config_version=2, active_provider=target, providers=profiles)
    _write_private_toml(path, raw)


def update_config_theme(config_path: Path, theme: str) -> None:
    if not is_valid_ui_theme(theme):
        raise ValueError("UI theme must be one of: dark, light.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    ui = raw.get("ui")
    ui_map = dict(ui) if isinstance(ui, Mapping) else {}
    ui_map["theme"] = theme
    ui_map.pop("textual_theme", None)
    raw["ui"] = ui_map
    _write_private_toml(path, raw)


def update_config_ui_interface(config_path: Path, interface: str) -> None:
    if not is_valid_ui_interface(interface):
        raise ValueError("UI interface must be one of: classic, modern.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    ui = raw.get("ui")
    ui_map = dict(ui) if isinstance(ui, Mapping) else {}
    ui_map["interface"] = interface
    raw["ui"] = ui_map
    _write_private_toml(path, raw)


def update_config_ui_choice(config_path: Path, *, interface: str, theme: str) -> None:
    if not is_valid_ui_interface(interface):
        raise ValueError("UI interface must be one of: classic, modern.")
    if not is_valid_ui_theme(theme):
        raise ValueError("UI theme must be one of: dark, light.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    ui = raw.get("ui")
    ui_map = dict(ui) if isinstance(ui, Mapping) else {}
    ui_map["interface"] = interface
    ui_map["theme"] = theme
    ui_map.pop("textual_theme", None)
    raw["ui"] = ui_map
    _write_private_toml(path, raw)


def update_config_textual_theme(config_path: Path, textual_theme: str) -> None:
    theme = textual_theme.strip()
    if not theme:
        raise ValueError("Textual theme must not be empty.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    ui = raw.get("ui")
    ui_map = dict(ui) if isinstance(ui, Mapping) else {}
    ui_map["textual_theme"] = theme
    raw["ui"] = ui_map
    _write_private_toml(path, raw)


def update_config_input_suggestions_enabled(config_path: Path, enabled: bool) -> None:
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    ui = raw.get("ui")
    ui_map = dict(ui) if isinstance(ui, Mapping) else {}
    ui_map["input_suggestions_enabled"] = bool(enabled)
    raw["ui"] = ui_map
    _write_private_toml(path, raw)


def update_config_view_mode(config_path: Path, view_mode: str) -> None:
    if not is_valid_ui_view_mode(view_mode):
        raise ValueError("View mode must be one of: concise, full.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    ui = raw.get("ui")
    ui_map = dict(ui) if isinstance(ui, Mapping) else {}
    ui_map["view_mode"] = view_mode
    raw["ui"] = ui_map
    _write_private_toml(path, raw)


def update_config_audit_mode(config_path: Path, audit_mode: str) -> None:
    if not is_valid_config_audit_mode(audit_mode):
        raise ValueError("Audit mode must be one of: normal, auto, yolo.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    audit = raw.get("audit")
    audit_map = dict(audit) if isinstance(audit, Mapping) else {}
    audit_map["mode"] = audit_mode
    raw["audit"] = audit_map
    _write_private_toml(path, raw)


def _read_toml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        loaded = tomllib.load(fh)
    return dict(loaded)


def _write_private_toml(path: Path, raw: Mapping[str, Any]) -> None:
    Settings.from_mapping(raw, env=os.environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".deepy-config-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(tomli_w.dumps(raw))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if item is None:
                continue
            cleaned = _drop_empty(item)
            if cleaned == {}:
                continue
            result[key] = cleaned
        return result
    if isinstance(value, list):
        return [_drop_empty(item) for item in value]
    return value
