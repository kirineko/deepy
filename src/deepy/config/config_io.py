from __future__ import annotations

import os
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import tomli_w

from deepy.audit import AuditMode, DEFAULT_AUDIT_MODE, is_valid_audit_mode

from .providers import (
    DEEPSEEK_REASONING_MODES,
    DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES,
    DEFAULT_COMPACT_TRIGGER_RATIO,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_INPUT_SUGGESTIONS_ENABLED,
    DEFAULT_MCP_CACHE_TOOLS_LIST,
    DEFAULT_MCP_CLEANUP_TIMEOUT_SECONDS,
    DEFAULT_MCP_CLIENT_SESSION_TIMEOUT_SECONDS,
    DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MCP_ENABLED,
    DEFAULT_PROVIDER,
    DEFAULT_RESERVED_CONTEXT_TOKENS,
    DEFAULT_UI_INTERFACE,
    DEFAULT_UI_THEME,
    DEFAULT_UI_VIEW_MODE,
    DEFAULT_WEB_SEARCH_SEARXNG_URL,
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
    reasoning_effort_for_mode,
    thinking_enabled_for_mode,
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
    env = env or os.environ
    if not config_path.exists():
        return Settings.from_mapping({}, path=config_path, env=env)

    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)
    return Settings.from_mapping(raw, path=config_path, env=env)


def settings_to_toml_dict(settings: Settings, *, reveal_secret: bool = False) -> dict[str, Any]:
    data = _drop_empty(asdict(settings))
    data.pop("path", None)
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
    api_key = settings.model.api_key
    if api_key:
        data["model"]["api_key"] = api_key if reveal_secret else mask_secret(api_key)
    data["model"]["thinking"] = settings.model.thinking_enabled
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
        if normalized in {number, f"{option_interface}-{option_theme}", f"{option_interface} {option_theme}"}:
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
        raise ValueError("Provider must be one of: deepseek, openrouter, xiaomi.")
    provider_info = provider_info_for(provider)
    if not is_valid_config_model_for_provider(model, provider):
        raise ValueError(
            "Model must be one of: " + ", ".join(model_info.name for model_info in provider_info.models)
        )
    mode = thinking_mode or provider_info.default_thinking_mode
    if not is_valid_thinking_mode_for_provider(mode, provider):
        raise ValueError(
            "Thinking mode must be one of: " + ", ".join(provider_info.thinking_modes)
        )
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    resolved_base_url = base_url or provider_info.default_base_url
    payload = {
        "model": {
            "provider": provider,
            "name": model,
            "base_url": resolved_base_url,
            "api_key": api_key,
            "thinking": thinking_enabled_for_mode(mode, provider),
            "reasoning_effort": reasoning_effort_for_mode(mode, provider),
        },
        "audit": {
            "mode": DEFAULT_AUDIT_MODE.value,
            "mcp_safe_tools": [],
        },
        "context": {
            "window_tokens": DEFAULT_CONTEXT_WINDOW_TOKENS,
            "compact_trigger_ratio": DEFAULT_COMPACT_TRIGGER_RATIO,
            "reserved_context_tokens": DEFAULT_RESERVED_CONTEXT_TOKENS,
            "compact_preserve_recent_messages": DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES,
        },
        "logging": {
            "debug": False,
        },
        "notify": {
            "enabled": False,
            "command": "",
        },
        "tools": {
            "web_search": {
                "searxng_url": DEFAULT_WEB_SEARCH_SEARXNG_URL,
            },
        },
        "mcp": {
            "enabled": DEFAULT_MCP_ENABLED,
            "connect_timeout_seconds": DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS,
            "cleanup_timeout_seconds": DEFAULT_MCP_CLEANUP_TIMEOUT_SECONDS,
            "client_session_timeout_seconds": DEFAULT_MCP_CLIENT_SESSION_TIMEOUT_SECONDS,
            "cache_tools_list": DEFAULT_MCP_CACHE_TOOLS_LIST,
            "allow_project_config": False,
            "prefer_mcp_web_search": True,
            "web_search": {
                "prefer_mcp": True,
                "preferred_server": "",
                "preferred_tools": [],
                "fallback_to_builtin": True,
            },
        },
        "ui": {
            "interface": interface,
            "theme": theme,
            "input_suggestions_enabled": DEFAULT_INPUT_SUGGESTIONS_ENABLED,
            "view_mode": DEFAULT_UI_VIEW_MODE,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)


def update_config_model_settings(
    config_path: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    reasoning_mode: str | None = None,
) -> None:
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    model_section = raw.get("model")
    model_map = dict(model_section) if isinstance(model_section, Mapping) else {}
    current = ModelConfig.from_mapping(model_map)
    active_provider = provider or current.provider
    if provider is not None and not is_supported_provider(provider):
        raise ValueError("Provider must be one of: deepseek, openrouter, xiaomi.")
    provider_info = provider_info_for(active_provider)
    active_model = model or current.name
    if model is None and provider is not None and not is_supported_model_for_provider(active_model, active_provider):
        active_model = provider_info.default_model
    # `/model` updates intentionally stay within Deepy's curated provider model catalog.
    if not is_supported_model_for_provider(active_model, active_provider):
        raise ValueError(
            "Model must be one of: " + ", ".join(model_info.name for model_info in provider_info.models)
        )
    active_mode = reasoning_mode or (
        current.reasoning_mode
        if is_valid_thinking_mode_for_provider(current.reasoning_mode, active_provider)
        else provider_info.default_thinking_mode
    )
    if not is_valid_thinking_mode_for_provider(active_mode, active_provider):
        if provider_info.thinking_modes == DEEPSEEK_REASONING_MODES:
            raise ValueError("Reasoning mode must be one of: none, high, max.")
        raise ValueError(
            "Thinking mode must be one of: " + ", ".join(provider_info.thinking_modes)
        )
    if provider is not None:
        model_map["provider"] = active_provider
        if base_url is None:
            model_map["base_url"] = provider_info.default_base_url
    if base_url is not None:
        model_map["base_url"] = base_url
    if model is not None:
        model_map["name"] = active_model
    elif provider is not None:
        model_map["name"] = active_model
    if reasoning_mode is not None or provider is not None:
        model_map["thinking"] = thinking_enabled_for_mode(active_mode, active_provider)
        model_map["reasoning_effort"] = reasoning_effort_for_mode(active_mode, active_provider)
    raw["model"] = model_map
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(raw), encoding="utf-8")
    os.chmod(path, 0o600)


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
