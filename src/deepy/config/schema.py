from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Self

from deepy.audit import AuditConfig

from .model_limits import ResolvedModelLimits

from .providers import (
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
    ProviderInfo,
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
    is_valid_config_model_for_provider,
    provider_info_for,
    resolve_provider,
)


@dataclass(frozen=True)
class ModelConfig:
    provider: str = DEFAULT_PROVIDER
    name: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = field(default=None, repr=False)
    thinking: bool | None = None
    reasoning_effort: str = "max"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], env: Mapping[str, str] | None = None) -> Self:
        from .profiles import resolve_profile_key
        from .providers import is_valid_thinking_mode_for_provider, reasoning_effort_for_mode

        provider = resolve_provider(_as_str(raw.get("provider"), DEFAULT_PROVIDER), None)
        info = provider_info_for(provider)
        name = _as_str(raw.get("model"), _as_str(raw.get("name"), info.default_model))
        if not is_valid_config_model_for_provider(name, provider):
            raise ValueError(f"Unsupported model {name} for {provider}.")
        mode = _as_str(raw.get("reasoning"), info.default_thinking_mode)
        if not is_valid_thinking_mode_for_provider(mode, provider):
            raise ValueError(f"Unsupported reasoning mode {mode} for {provider}.")
        return cls(
            provider=provider,
            name=name,
            base_url=_as_str(raw.get("base_url"), info.default_base_url),
            api_key=resolve_profile_key(provider, raw, env or {}),
            thinking=mode not in {"none", "disabled"},
            reasoning_effort=reasoning_effort_for_mode(mode, provider),
        )

    @property
    def thinking_enabled(self) -> bool:
        if self.thinking is not None:
            return self.thinking
        return self.reasoning_effort not in {"none", "disabled"}

    @property
    def reasoning_mode(self) -> str:
        if self.provider == "mimo":
            return "enabled" if self.thinking_enabled else "disabled"
        return self.reasoning_effort if self.thinking_enabled else "none"

    @property
    def provider_info(self) -> ProviderInfo:
        return provider_info_for(self.provider)


@dataclass(frozen=True)
class ContextConfig:
    window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    explicit_window_tokens: int | None = None
    window_is_resolved: bool = False
    compact_trigger_ratio: float = DEFAULT_COMPACT_TRIGGER_RATIO
    reserved_context_tokens: int = DEFAULT_RESERVED_CONTEXT_TOKENS
    compact_preserve_recent_messages: int = DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES
    compact_preserve_recent_tokens: int | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        from .model_limits import positive_limit

        if "window_tokens" in raw:
            positive_limit(raw["window_tokens"], "context.window_tokens")
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
            explicit_window_tokens=raw.get("window_tokens"),
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
    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls()


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
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    provider_keys: dict[str, str | None] = field(default_factory=dict, repr=False)
    audit: AuditConfig = field(default_factory=AuditConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    mcp: McpConfig = field(default_factory=McpConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    path: Path | None = None

    def model_for_provider(self, provider: str) -> ModelConfig:
        from dataclasses import replace

        if provider == self.model.provider:
            return self.model
        model = ModelConfig.from_mapping({**self.profiles.get(provider, {}), "provider": provider})
        return replace(model, api_key=self.provider_keys.get(provider) or model.api_key)

    @property
    def model_limits(self) -> "ResolvedModelLimits":
        from .model_limits import resolve_model_limits

        return resolve_model_limits(
            self.model.provider, self.model.name,
            global_cap=self.context.explicit_window_tokens or (
                self.context.window_tokens if not self.context.window_is_resolved
                and self.context.window_tokens != DEFAULT_CONTEXT_WINDOW_TOKENS else None),
            overrides=self.profiles.get(self.model.provider, {}).get("model_limits", {}).get(self.model.name),
            reserve_floor=self.context.reserved_context_tokens,
        )

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        path: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> Self:
        from .profiles import parse_profiles, resolve_profile_key

        profiles, active = parse_profiles(raw)
        for provider, profile in profiles.items():
            ModelConfig.from_mapping({**profile, "provider": provider}, env=env)
        keys = {
            provider: resolve_profile_key(provider, profiles.get(provider, {}), env or {})
            for provider in ("deepseek", "mimo", "kimi", "cli_proxy")
        }
        context = ContextConfig.from_mapping(_as_mapping(raw.get("context")))
        from .model_limits import validate_profile_limits

        for provider, profile in profiles.items():
            validate_profile_limits(provider, profile, global_cap=context.explicit_window_tokens,
                                    reserve_floor=context.reserved_context_tokens)
        result = cls(
            profiles=profiles,
            provider_keys=keys,
            audit=AuditConfig.from_mapping(_as_mapping(raw.get("audit"))),
            model=ModelConfig.from_mapping(
                {**profiles.get(active, {}), "provider": active}, env=env
            ),
            context=context,
            logging=LoggingConfig.from_mapping(_as_mapping(raw.get("logging"))),
            notify=NotifyConfig.from_mapping(_as_mapping(raw.get("notify"))),
            tools=ToolsConfig.from_mapping(_as_mapping(raw.get("tools"))),
            mcp=McpConfig.from_mapping(_as_mapping(raw.get("mcp"))),
            ui=UiConfig.from_mapping(_as_mapping(raw.get("ui"))),
            path=path,
        )
        return replace(result, context=replace(context, window_tokens=result.model_limits.window_tokens, window_is_resolved=True))
