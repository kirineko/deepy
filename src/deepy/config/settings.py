from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Mapping, Self

import tomli_w

from deepy.audit import AuditConfig, AuditMode, DEFAULT_AUDIT_MODE, is_valid_audit_mode

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_048_576
DEFAULT_COMPACT_TRIGGER_RATIO = 0.8
DEFAULT_RESERVED_CONTEXT_TOKENS = 50_000
DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES = 2
DEFAULT_WEB_SEARCH_SEARXNG_URL = "https://s.kirineko.tech/"
DEFAULT_UI_THEME = "dark"
DEFAULT_MCP_ENABLED = True
DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS = 10.0
DEFAULT_MCP_CLEANUP_TIMEOUT_SECONDS = 10.0
DEFAULT_MCP_CLIENT_SESSION_TIMEOUT_SECONDS = 30.0
DEFAULT_MCP_CACHE_TOOLS_LIST = True
DEFAULT_INPUT_SUGGESTIONS_ENABLED = True
DEFAULT_UI_VIEW_MODE = "concise"
DEFAULT_PROVIDER = "deepseek"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_XIAOMI_BASE_URL = "https://api.xiaomimimo.com/v1"
DEEPSEEK_REASONING_EFFORTS = {"high", "max"}
SWITCH_ONLY_REASONING_EFFORTS = {"enabled", "none"}
OPENROUTER_REASONING_MODES = (
    "enabled",
    "disabled",
    "xhigh",
    "high",
    "medium",
    "low",
    "minimal",
    "none",
)
OPENROUTER_REASONING_EFFORTS = set(OPENROUTER_REASONING_MODES)
REASONING_EFFORTS = DEEPSEEK_REASONING_EFFORTS | SWITCH_ONLY_REASONING_EFFORTS | OPENROUTER_REASONING_EFFORTS
DEEPSEEK_REASONING_MODES = ("none", "high", "max")
SWITCH_ONLY_THINKING_MODES = ("disabled", "enabled")
REASONING_MODES = set(DEEPSEEK_REASONING_MODES)
THINKING_MODES = set(DEEPSEEK_REASONING_MODES) | set(SWITCH_ONLY_THINKING_MODES) | OPENROUTER_REASONING_EFFORTS
PROVIDERS = {"deepseek", "openrouter", "xiaomi"}
UI_THEMES = {"dark", "light"}
UI_THEME_OPTIONS = (("1", "dark"), ("2", "light"))
UI_VIEW_MODES = {"concise", "full"}


@dataclass(frozen=True)
class ModelInfo:
    name: str
    label: str
    description: str
    supports_thinking: bool = True
    default_reasoning_mode: str = "max"


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    label: str
    description: str
    default_base_url: str
    models: tuple[ModelInfo, ...]
    thinking_modes: tuple[str, ...]
    default_model: str
    default_thinking_mode: str
    sends_reasoning_effort: bool = True
    api_key_url: str | None = None


DeepSeekModelInfo = ModelInfo


DEEPSEEK_MODEL_CATALOG = (
    ModelInfo(
        name="deepseek-v4-pro",
        label="DeepSeek V4 Pro",
        description="Higher quality for agentic coding and complex reasoning.",
    ),
    ModelInfo(
        name="deepseek-v4-flash",
        label="DeepSeek V4 Flash",
        description="Lower latency and cost for faster everyday turns.",
    ),
)
OPENROUTER_MODEL_CATALOG = (
    ModelInfo(
        name="xiaomi/mimo-v2.5-pro",
        label="MiMo V2.5 Pro",
        description="Xiaomi MiMo V2.5 Pro via OpenRouter.",
        default_reasoning_mode="enabled",
    ),
    ModelInfo(
        name="xiaomi/mimo-v2.5",
        label="MiMo V2.5",
        description="Xiaomi MiMo V2.5 via OpenRouter.",
        default_reasoning_mode="enabled",
    ),
)
XIAOMI_MODEL_CATALOG = (
    ModelInfo(
        name="mimo-v2.5-pro",
        label="MiMo V2.5 Pro",
        description="Xiaomi official MiMo V2.5 Pro.",
        default_reasoning_mode="enabled",
    ),
    ModelInfo(
        name="mimo-v2.5",
        label="MiMo V2.5",
        description="Xiaomi official MiMo V2.5.",
        default_reasoning_mode="enabled",
    ),
)
PROVIDER_CATALOG = (
    ProviderInfo(
        id="deepseek",
        label="DeepSeek",
        description="DeepSeek official OpenAI-compatible API.",
        default_base_url=DEFAULT_BASE_URL,
        models=DEEPSEEK_MODEL_CATALOG,
        thinking_modes=DEEPSEEK_REASONING_MODES,
        default_model=DEFAULT_MODEL,
        default_thinking_mode="max",
        api_key_url="https://platform.deepseek.com/api_keys",
    ),
    ProviderInfo(
        id="openrouter",
        label="OpenRouter",
        description="OpenRouter gateway for Xiaomi MiMo models.",
        default_base_url=DEFAULT_OPENROUTER_BASE_URL,
        models=OPENROUTER_MODEL_CATALOG,
        thinking_modes=OPENROUTER_REASONING_MODES,
        default_model="xiaomi/mimo-v2.5-pro",
        default_thinking_mode="enabled",
        api_key_url="https://openrouter.ai/workspaces/default/keys",
    ),
    ProviderInfo(
        id="xiaomi",
        label="Xiaomi",
        description="Xiaomi official MiMo OpenAI-compatible API.",
        default_base_url=DEFAULT_XIAOMI_BASE_URL,
        models=XIAOMI_MODEL_CATALOG,
        thinking_modes=SWITCH_ONLY_THINKING_MODES,
        default_model="mimo-v2.5-pro",
        default_thinking_mode="enabled",
        sends_reasoning_effort=False,
        api_key_url="https://platform.xiaomimimo.com/console/api-keys",
    ),
)
PROVIDER_BY_ID = {provider.id: provider for provider in PROVIDER_CATALOG}
SUPPORTED_DEEPSEEK_MODELS = frozenset(model.name for model in DEEPSEEK_MODEL_CATALOG)
SUPPORTED_MODELS_BY_PROVIDER = {
    provider.id: frozenset(model.name for model in provider.models)
    for provider in PROVIDER_CATALOG
}


def provider_info_for(provider: str | None) -> ProviderInfo:
    return PROVIDER_BY_ID.get(provider or DEFAULT_PROVIDER, PROVIDER_BY_ID[DEFAULT_PROVIDER])


def resolve_provider(raw_provider: str | None, base_url: str | None) -> str:
    provider = (raw_provider or "").strip().lower()
    if provider in PROVIDERS:
        return provider
    inferred = infer_provider_from_base_url(base_url)
    return inferred or DEFAULT_PROVIDER


def infer_provider_from_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if host == "api.deepseek.com":
        return "deepseek"
    if host == "openrouter.ai":
        return "openrouter"
    if host == "api.xiaomimimo.com":
        return "xiaomi"
    return None


def _raw_provider_value(raw: Mapping[str, Any], env: Mapping[str, str]) -> str | None:
    provider = _as_str(env.get("DEEPY_PROVIDER"), _as_str(raw.get("provider"), ""))
    return provider.lower() if provider else None


def is_supported_provider(value: str) -> bool:
    return value in PROVIDERS


def is_supported_model_for_provider(model: str, provider: str) -> bool:
    return model in SUPPORTED_MODELS_BY_PROVIDER.get(provider, ())


def allows_custom_model_for_provider(provider: str) -> bool:
    return provider == "openrouter"


def is_valid_config_model_for_provider(model: str, provider: str) -> bool:
    return bool(model.strip()) and (
        allows_custom_model_for_provider(provider)
        or is_supported_model_for_provider(model, provider)
    )


def default_model_for_provider(provider: str) -> str:
    return provider_info_for(provider).default_model


def default_base_url_for_provider(provider: str) -> str:
    return provider_info_for(provider).default_base_url


def default_thinking_mode_for_provider(provider: str) -> str:
    return provider_info_for(provider).default_thinking_mode


def thinking_modes_for_provider(provider: str) -> tuple[str, ...]:
    return provider_info_for(provider).thinking_modes


def is_valid_thinking_mode_for_provider(value: str, provider: str) -> bool:
    return value in thinking_modes_for_provider(provider)


def normalize_reasoning_effort(
    value: str,
    *,
    provider: str,
    thinking: bool | None,
) -> str:
    provider_info = provider_info_for(provider)
    if provider == "openrouter":
        if thinking is False or value in {"none", "disabled"}:
            return "none"
        if value == "enabled":
            return "enabled"
        if value in OPENROUTER_REASONING_EFFORTS:
            return value
        return provider_info.default_thinking_mode
    if provider_info.thinking_modes == SWITCH_ONLY_THINKING_MODES:
        if thinking is False or value in {"none", "disabled"}:
            return "none"
        if thinking is True or value == "enabled":
            return "enabled"
        return provider_info.default_thinking_mode
    if value in DEEPSEEK_REASONING_EFFORTS:
        return value
    return provider_info.default_thinking_mode


def thinking_enabled_for_mode(mode: str, provider: str) -> bool:
    if provider == "openrouter":
        return mode not in {"none", "disabled"}
    if provider_info_for(provider).thinking_modes == SWITCH_ONLY_THINKING_MODES:
        return mode != "disabled"
    return mode != "none"


def reasoning_effort_for_mode(mode: str, provider: str) -> str:
    if provider == "openrouter":
        if mode in {"none", "disabled"}:
            return "none"
        if mode == "enabled":
            return "enabled"
        if mode in OPENROUTER_REASONING_EFFORTS:
            return mode
        return provider_info_for(provider).default_thinking_mode
    if provider_info_for(provider).thinking_modes == SWITCH_ONLY_THINKING_MODES:
        return "none" if mode == "disabled" else "enabled"
    return mode if mode in DEEPSEEK_REASONING_EFFORTS else "max"


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


def _as_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


@dataclass(frozen=True)
class ModelConfig:
    provider: str = DEFAULT_PROVIDER
    name: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = None
    thinking: bool | None = None
    reasoning_effort: str = "max"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], env: Mapping[str, str] | None = None) -> Self:
        env = env or {}
        base_url = _as_str(
            env.get("DEEPY_BASE_URL"),
            _as_str(raw.get("base_url"), DEFAULT_BASE_URL),
        )
        raw_provider = _raw_provider_value(raw, env)
        inferred_provider = infer_provider_from_base_url(base_url)
        provider = resolve_provider(raw_provider, base_url)
        provider_was_explicit_or_inferred = raw_provider in PROVIDERS or inferred_provider is not None
        provider_info = provider_info_for(provider)
        name = _as_str(env.get("DEEPY_MODEL"), _as_str(raw.get("name"), provider_info.default_model))
        if (
            provider_was_explicit_or_inferred
            and provider in PROVIDERS
            and not is_valid_config_model_for_provider(name, provider)
        ):
            name = provider_info.default_model
        api_key = _as_str(env.get("DEEPY_API_KEY"), _as_str(raw.get("api_key"), "")) or None
        thinking_value = raw.get("thinking")
        thinking = thinking_value if isinstance(thinking_value, bool) else None
        effort = normalize_reasoning_effort(
            _as_str(raw.get("reasoning_effort"), provider_info.default_thinking_mode),
            provider=provider,
            thinking=thinking,
        )

        return cls(
            provider=provider,
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
        return self.provider_info.default_thinking_mode != "none"

    @property
    def reasoning_mode(self) -> str:
        if self.provider == "openrouter":
            if not self.thinking_enabled:
                return "none"
            return (
                self.reasoning_effort
                if self.reasoning_effort in OPENROUTER_REASONING_EFFORTS
                else self.provider_info.default_thinking_mode
            )
        if self.provider_info.thinking_modes == SWITCH_ONLY_THINKING_MODES:
            return "enabled" if self.thinking_enabled else "disabled"
        if not self.thinking_enabled:
            return "none"
        return self.reasoning_effort if self.reasoning_effort in DEEPSEEK_REASONING_EFFORTS else "max"

    @property
    def provider_info(self) -> ProviderInfo:
        return provider_info_for(self.provider)


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
class TestShellToolConfig:
    allow_patterns: tuple[str, ...] = ()
    approval_required_patterns: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            allow_patterns=_as_string_tuple(raw.get("allow_patterns")),
            approval_required_patterns=_as_string_tuple(raw.get("approval_required_patterns")),
        )


@dataclass(frozen=True)
class ToolsConfig:
    web_search: WebSearchToolConfig = field(default_factory=WebSearchToolConfig)
    test_shell: TestShellToolConfig = field(default_factory=TestShellToolConfig)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            web_search=WebSearchToolConfig.from_mapping(_as_mapping(raw.get("web_search"))),
            test_shell=TestShellToolConfig.from_mapping(_as_mapping(raw.get("test_shell"))),
        )


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
    input_suggestions_enabled: bool = DEFAULT_INPUT_SUGGESTIONS_ENABLED
    view_mode: str = DEFAULT_UI_VIEW_MODE

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        theme = raw.get("theme")
        input_suggestions_enabled = _as_bool(
            raw.get("input_suggestions_enabled"),
            DEFAULT_INPUT_SUGGESTIONS_ENABLED,
        )
        view_mode = _as_str(raw.get("view_mode"), DEFAULT_UI_VIEW_MODE)
        if view_mode not in UI_VIEW_MODES:
            view_mode = DEFAULT_UI_VIEW_MODE
        if isinstance(theme, str) and theme.strip() == "auto":
            return cls(
                theme=DEFAULT_UI_THEME,
                theme_configured=True,
                input_suggestions_enabled=input_suggestions_enabled,
                view_mode=view_mode,
            )
        if isinstance(theme, str) and theme.strip() in UI_THEMES:
            return cls(
                theme=theme.strip(),
                theme_configured=True,
                input_suggestions_enabled=input_suggestions_enabled,
                view_mode=view_mode,
            )
        return cls(input_suggestions_enabled=input_suggestions_enabled, view_mode=view_mode)


@dataclass(frozen=True)
class Settings:
    audit: AuditConfig = field(default_factory=AuditConfig)
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
            audit=AuditConfig.from_mapping(_as_mapping(raw.get("audit"))),
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


def write_config(
    config_path: Path,
    *,
    api_key: str,
    provider: str = DEFAULT_PROVIDER,
    model: str,
    base_url: str | None = None,
    theme: str,
    thinking_mode: str | None = None,
) -> None:
    if not is_valid_ui_theme(theme):
        raise ValueError("UI theme must be one of: dark, light.")
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
