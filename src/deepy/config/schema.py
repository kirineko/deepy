from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Self

from deepy.audit import AuditConfig

from .providers import (
    DEEPSEEK_REASONING_EFFORTS,
    DEFAULT_BASE_URL,
    DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES,
    DEFAULT_COMPACT_TRIGGER_RATIO,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_INPUT_SUGGESTIONS_ENABLED,
    DEFAULT_MCP_CACHE_TOOLS_LIST,
    DEFAULT_MCP_CLEANUP_TIMEOUT_SECONDS,
    DEFAULT_MCP_CLIENT_SESSION_TIMEOUT_SECONDS,
    DEFAULT_MCP_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MCP_ENABLED,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_RESERVED_CONTEXT_TOKENS,
    DEFAULT_UI_INTERFACE,
    DEFAULT_UI_THEME,
    DEFAULT_UI_VIEW_MODE,
    DEFAULT_WEB_SEARCH_SEARXNG_URL,
    LOCALHOST_REASONING_EFFORTS,
    OPENROUTER_REASONING_EFFORTS,
    PROVIDERS,
    ProviderInfo,
    SWITCH_ONLY_THINKING_MODES,
    UI_INTERFACES,
    UI_THEMES,
    UI_VIEW_MODES,
    _as_bool,
    _as_float,
    _as_int,
    _as_mapping,
    _as_optional_str,
    _as_str,
    _as_string_tuple,
    _raw_provider_value,
    infer_provider_from_base_url,
    is_valid_config_model_for_provider,
    normalize_reasoning_effort,
    provider_info_for,
    resolve_provider,
)

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
        if self.provider == "localhost":
            if not self.thinking_enabled:
                return "none"
            return (
                self.reasoning_effort
                if self.reasoning_effort in LOCALHOST_REASONING_EFFORTS
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
    interface: str = DEFAULT_UI_INTERFACE
    theme_configured: bool = False
    textual_theme: str | None = None
    input_suggestions_enabled: bool = DEFAULT_INPUT_SUGGESTIONS_ENABLED
    view_mode: str = DEFAULT_UI_VIEW_MODE

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        theme = raw.get("theme")
        interface = _as_str(raw.get("interface"), DEFAULT_UI_INTERFACE)
        if interface not in UI_INTERFACES:
            interface = DEFAULT_UI_INTERFACE
        textual_theme = _as_optional_str(raw.get("textual_theme"))
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
                interface=interface,
                theme_configured=True,
                textual_theme=textual_theme,
                input_suggestions_enabled=input_suggestions_enabled,
                view_mode=view_mode,
            )
        if isinstance(theme, str) and theme.strip() in UI_THEMES:
            return cls(
                theme=theme.strip(),
                interface=interface,
                theme_configured=True,
                textual_theme=textual_theme,
                input_suggestions_enabled=input_suggestions_enabled,
                view_mode=view_mode,
            )
        return cls(
            textual_theme=textual_theme,
            interface=interface,
            input_suggestions_enabled=input_suggestions_enabled,
            view_mode=view_mode,
        )


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
