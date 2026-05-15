from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Self

import tomli_w

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_048_576
DEFAULT_COMPACT_TRIGGER_RATIO = 0.8
DEFAULT_RESERVED_CONTEXT_TOKENS = 50_000
DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES = 2
DEFAULT_WEB_SEARCH_SEARXNG_URL = "https://s.kirineko.tech/"
DEFAULT_UI_THEME = "auto"
DEFAULT_MCP_ENABLED = True
DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS = 10.0
DEFAULT_MCP_CLEANUP_TIMEOUT_SECONDS = 10.0
DEFAULT_MCP_CLIENT_SESSION_TIMEOUT_SECONDS = 30.0
DEFAULT_MCP_CACHE_TOOLS_LIST = True
REASONING_EFFORTS = {"high", "max"}
REASONING_MODES = {"none", "high", "max"}
UI_THEMES = {"auto", "dark", "light"}
UI_THEME_OPTIONS = (("1", "auto"), ("2", "dark"), ("3", "light"))


@dataclass(frozen=True)
class DeepSeekModelInfo:
    name: str
    label: str
    description: str
    supports_thinking: bool = True
    default_reasoning_mode: str = "max"


DEEPSEEK_MODEL_CATALOG = (
    DeepSeekModelInfo(
        name="deepseek-v4-pro",
        label="DeepSeek V4 Pro",
        description="Higher quality for agentic coding and complex reasoning.",
    ),
    DeepSeekModelInfo(
        name="deepseek-v4-flash",
        label="DeepSeek V4 Flash",
        description="Lower latency and cost for faster everyday turns.",
    ),
)
SUPPORTED_DEEPSEEK_MODELS = frozenset(model.name for model in DEEPSEEK_MODEL_CATALOG)


def default_config_path() -> Path:
    return Path.home() / ".deepy" / "config.toml"


def default_mcp_config_path(config_path: Path | None = None) -> Path:
    if config_path is not None:
        return config_path.expanduser().parent / "mcp.json"
    return Path.home() / ".deepy" / "mcp.json"


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float) and value > 0:
        return float(value)
    return default


def _as_str(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


@dataclass(frozen=True)
class ModelConfig:
    name: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = None
    thinking: bool | None = None
    reasoning_effort: str = "max"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], env: Mapping[str, str] | None = None) -> Self:
        env = env or {}
        name = _as_str(env.get("DEEPY_MODEL"), _as_str(raw.get("name"), DEFAULT_MODEL))
        base_url = _as_str(
            env.get("DEEPY_BASE_URL"),
            _as_str(raw.get("base_url"), DEFAULT_BASE_URL),
        )
        api_key = _as_str(env.get("DEEPY_API_KEY"), _as_str(raw.get("api_key"), "")) or None
        effort = _as_str(raw.get("reasoning_effort"), "max")
        if effort not in REASONING_EFFORTS:
            effort = "max"

        thinking_value = raw.get("thinking")
        thinking = thinking_value if isinstance(thinking_value, bool) else None

        return cls(
            name=name,
            base_url=base_url,
            api_key=api_key,
            thinking=thinking,
            reasoning_effort=effort,
        )

    @property
    def thinking_enabled(self) -> bool:
        if self.thinking is not None:
            return self.thinking
        return self.name.lower() in SUPPORTED_DEEPSEEK_MODELS

    @property
    def reasoning_mode(self) -> str:
        if not self.thinking_enabled:
            return "none"
        return self.reasoning_effort if self.reasoning_effort in REASONING_EFFORTS else "max"


@dataclass(frozen=True)
class ContextConfig:
    window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    compact_trigger_ratio: float = DEFAULT_COMPACT_TRIGGER_RATIO
    reserved_context_tokens: int = DEFAULT_RESERVED_CONTEXT_TOKENS
    compact_preserve_recent_messages: int = DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES
    compact_preserve_recent_tokens: int | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        window_tokens = _as_int(raw.get("window_tokens"), DEFAULT_CONTEXT_WINDOW_TOKENS)
        ratio = _as_float(raw.get("compact_trigger_ratio"), DEFAULT_COMPACT_TRIGGER_RATIO)
        if ratio <= 0 or ratio > 1:
            ratio = DEFAULT_COMPACT_TRIGGER_RATIO
        reserved_context_tokens = _as_int(
            raw.get("reserved_context_tokens"),
            DEFAULT_RESERVED_CONTEXT_TOKENS,
        )
        preserve_recent_messages = _as_int(
            raw.get("compact_preserve_recent_messages"),
            DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES,
        )
        preserve_recent_tokens_raw = raw.get("compact_preserve_recent_tokens")
        preserve_recent_tokens = (
            _as_int(preserve_recent_tokens_raw, 0)
            if preserve_recent_tokens_raw is not None
            else None
        )
        return cls(
            window_tokens=window_tokens,
            compact_trigger_ratio=ratio,
            reserved_context_tokens=reserved_context_tokens,
            compact_preserve_recent_messages=preserve_recent_messages,
            compact_preserve_recent_tokens=preserve_recent_tokens or None,
        )

    @property
    def resolved_compact_threshold(self) -> int:
        return int(self.window_tokens * self.compact_trigger_ratio + 0.999999)


@dataclass(frozen=True)
class LoggingConfig:
    debug: bool = False

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(debug=_as_bool(raw.get("debug"), False))


@dataclass(frozen=True)
class NotifyConfig:
    enabled: bool = False
    command: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        command = _as_str(raw.get("command")) or None
        return cls(enabled=_as_bool(raw.get("enabled"), bool(command)), command=command)


@dataclass(frozen=True)
class WebSearchToolConfig:
    searxng_url: str | None = DEFAULT_WEB_SEARCH_SEARXNG_URL

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            searxng_url=_as_str(raw.get("searxng_url"), DEFAULT_WEB_SEARCH_SEARXNG_URL),
        )


@dataclass(frozen=True)
class ToolsConfig:
    web_search: WebSearchToolConfig = field(default_factory=WebSearchToolConfig)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(web_search=WebSearchToolConfig.from_mapping(_as_mapping(raw.get("web_search"))))


@dataclass(frozen=True)
class McpWebSearchConfig:
    prefer_mcp: bool = True
    preferred_server: str | None = None
    preferred_tools: tuple[str, ...] = ()
    fallback_to_builtin: bool = True

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        tools = raw.get("preferred_tools")
        preferred_tools = (
            tuple(item.strip() for item in tools if isinstance(item, str) and item.strip())
            if isinstance(tools, list)
            else ()
        )
        return cls(
            prefer_mcp=_as_bool(raw.get("prefer_mcp"), True),
            preferred_server=_as_str(raw.get("preferred_server")) or None,
            preferred_tools=preferred_tools,
            fallback_to_builtin=_as_bool(raw.get("fallback_to_builtin"), True),
        )


@dataclass(frozen=True)
class McpConfig:
    enabled: bool = DEFAULT_MCP_ENABLED
    connect_timeout_seconds: float = DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS
    cleanup_timeout_seconds: float = DEFAULT_MCP_CLEANUP_TIMEOUT_SECONDS
    client_session_timeout_seconds: float = DEFAULT_MCP_CLIENT_SESSION_TIMEOUT_SECONDS
    cache_tools_list: bool = DEFAULT_MCP_CACHE_TOOLS_LIST
    allow_project_config: bool = False
    prefer_mcp_web_search: bool = True
    web_search: McpWebSearchConfig = field(default_factory=McpWebSearchConfig)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            enabled=_as_bool(raw.get("enabled"), DEFAULT_MCP_ENABLED),
            connect_timeout_seconds=_as_float(
                raw.get("connect_timeout_seconds"),
                DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS,
            ),
            cleanup_timeout_seconds=_as_float(
                raw.get("cleanup_timeout_seconds"),
                DEFAULT_MCP_CLEANUP_TIMEOUT_SECONDS,
            ),
            client_session_timeout_seconds=_as_float(
                raw.get("client_session_timeout_seconds"),
                DEFAULT_MCP_CLIENT_SESSION_TIMEOUT_SECONDS,
            ),
            cache_tools_list=_as_bool(raw.get("cache_tools_list"), DEFAULT_MCP_CACHE_TOOLS_LIST),
            allow_project_config=_as_bool(raw.get("allow_project_config"), False),
            prefer_mcp_web_search=_as_bool(raw.get("prefer_mcp_web_search"), True),
            web_search=McpWebSearchConfig.from_mapping(_as_mapping(raw.get("web_search"))),
        )


@dataclass(frozen=True)
class UiConfig:
    theme: str = DEFAULT_UI_THEME
    theme_configured: bool = False

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        theme = raw.get("theme")
        if isinstance(theme, str) and theme.strip() in UI_THEMES:
            return cls(theme=theme.strip(), theme_configured=True)
        return cls()


@dataclass(frozen=True)
class Settings:
    model: ModelConfig = field(default_factory=ModelConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    mcp: McpConfig = field(default_factory=McpConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    path: Path | None = None

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        path: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> Self:
        return cls(
            model=ModelConfig.from_mapping(_as_mapping(raw.get("model")), env=env),
            context=ContextConfig.from_mapping(_as_mapping(raw.get("context"))),
            logging=LoggingConfig.from_mapping(_as_mapping(raw.get("logging"))),
            notify=NotifyConfig.from_mapping(_as_mapping(raw.get("notify"))),
            tools=ToolsConfig.from_mapping(_as_mapping(raw.get("tools"))),
            mcp=McpConfig.from_mapping(_as_mapping(raw.get("mcp"))),
            ui=UiConfig.from_mapping(_as_mapping(raw.get("ui"))),
            path=path,
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
    api_key = settings.model.api_key
    if api_key:
        data["model"]["api_key"] = api_key if reveal_secret else mask_secret(api_key)
    data["model"]["thinking"] = settings.model.thinking_enabled
    return _drop_empty(data)


def is_valid_ui_theme(value: str) -> bool:
    return value in UI_THEMES


def is_supported_deepseek_model(value: str) -> bool:
    return value in SUPPORTED_DEEPSEEK_MODELS


def is_valid_reasoning_mode(value: str) -> bool:
    return value in REASONING_MODES


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


def write_config(
    config_path: Path,
    *,
    api_key: str,
    model: str,
    base_url: str,
    theme: str,
) -> None:
    if not is_valid_ui_theme(theme):
        raise ValueError("UI theme must be one of: auto, dark, light.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    payload = {
        "model": {
            "name": model,
            "base_url": base_url,
            "api_key": api_key,
            "thinking": True,
            "reasoning_effort": "max",
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
            "theme": theme,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o600)


def update_config_model_settings(
    config_path: Path,
    *,
    model: str | None = None,
    reasoning_mode: str | None = None,
) -> None:
    if model is not None and not is_supported_deepseek_model(model):
        raise ValueError(
            "Model must be one of: " + ", ".join(model_info.name for model_info in DEEPSEEK_MODEL_CATALOG)
        )
    if reasoning_mode is not None and not is_valid_reasoning_mode(reasoning_mode):
        raise ValueError("Reasoning mode must be one of: none, high, max.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    model_section = raw.get("model")
    model_map = dict(model_section) if isinstance(model_section, Mapping) else {}
    if model is not None:
        model_map["name"] = model
    if reasoning_mode is not None:
        if reasoning_mode == "none":
            model_map["thinking"] = False
        else:
            model_map["thinking"] = True
            model_map["reasoning_effort"] = reasoning_mode
    raw["model"] = model_map
    _write_private_toml(path, raw)


def update_config_theme(config_path: Path, theme: str) -> None:
    if not is_valid_ui_theme(theme):
        raise ValueError("UI theme must be one of: auto, dark, light.")
    path = config_path.expanduser()
    if path.suffix == ".json":
        raise ValueError("Deepy only supports TOML config files; JSON config is not supported.")
    raw = _read_toml_mapping(path)
    ui = raw.get("ui")
    ui_map = dict(ui) if isinstance(ui, Mapping) else {}
    ui_map["theme"] = theme
    raw["ui"] = ui_map
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
