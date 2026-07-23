from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_048_576
DEFAULT_COMPACT_TRIGGER_RATIO = 0.8
DEFAULT_RESERVED_CONTEXT_TOKENS = 50_000
DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES = 2
DEFAULT_WEB_SEARCH_SEARXNG_URL = "https://s.kirineko.tech/"
DEFAULT_UI_THEME = "dark"
DEFAULT_UI_INTERFACE = "classic"
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
DEFAULT_LOCALHOST_BASE_URL = "http://127.0.0.1:8317/v1"
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
LOCALHOST_REASONING_MODES = ("none", "low", "medium", "high", "xhigh")
LOCALHOST_REASONING_EFFORTS = set(LOCALHOST_REASONING_MODES)
REASONING_EFFORTS = (
    DEEPSEEK_REASONING_EFFORTS
    | SWITCH_ONLY_REASONING_EFFORTS
    | OPENROUTER_REASONING_EFFORTS
    | LOCALHOST_REASONING_EFFORTS
)
DEEPSEEK_REASONING_MODES = ("none", "high", "max")
SWITCH_ONLY_THINKING_MODES = ("disabled", "enabled")
REASONING_MODES = set(DEEPSEEK_REASONING_MODES)
THINKING_MODES = (
    set(DEEPSEEK_REASONING_MODES)
    | set(SWITCH_ONLY_THINKING_MODES)
    | OPENROUTER_REASONING_EFFORTS
    | LOCALHOST_REASONING_EFFORTS
)
PROVIDERS = {"deepseek", "openrouter", "xiaomi", "localhost"}
PROVIDER_API_CHAT_COMPLETIONS = "chat_completions"
PROVIDER_API_RESPONSES = "responses"
UI_THEMES = {"dark", "light"}
UI_THEME_OPTIONS = (("1", "dark"), ("2", "light"))
UI_INTERFACES = {"classic", "modern"}
UI_INTERFACE_OPTIONS = (("1", "classic"), ("2", "modern"))
UI_SETUP_OPTIONS = (
    ("1", "classic", "dark"),
    ("2", "classic", "light"),
    ("3", "modern", "dark"),
    ("4", "modern", "light"),
)
UI_VIEW_MODES = {"concise", "full"}


@dataclass(frozen=True)
class ModelInfo:
    name: str
    label: str
    description: str
    supports_thinking: bool = True
    supports_image_input: bool = False
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
    api: str = PROVIDER_API_CHAT_COMPLETIONS
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
        supports_image_input=True,
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
        supports_image_input=True,
        default_reasoning_mode="enabled",
    ),
)
LOCALHOST_MODEL_CATALOG = (
    ModelInfo(
        name="gpt-5.6-sol",
        label="GPT-5.6 Sol",
        description="Flagship GPT-5.6 capability via local CLIProxyAPI.",
        supports_image_input=True,
        default_reasoning_mode="medium",
    ),
    ModelInfo(
        name="gpt-5.6-terra",
        label="GPT-5.6 Terra",
        description="Balanced GPT-5.6 performance and cost via local CLIProxyAPI.",
        supports_image_input=True,
        default_reasoning_mode="medium",
    ),
    ModelInfo(
        name="gpt-5.6-luna",
        label="GPT-5.6 Luna",
        description="Efficient high-volume GPT-5.6 via local CLIProxyAPI.",
        supports_image_input=True,
        default_reasoning_mode="medium",
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
    ProviderInfo(
        id="localhost",
        label="Localhost",
        description="Local CLIProxyAPI OpenAI Responses endpoint for GPT-5.6.",
        default_base_url=DEFAULT_LOCALHOST_BASE_URL,
        models=LOCALHOST_MODEL_CATALOG,
        thinking_modes=LOCALHOST_REASONING_MODES,
        default_model="gpt-5.6-terra",
        default_thinking_mode="medium",
        api=PROVIDER_API_RESPONSES,
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
    if host in {"127.0.0.1", "localhost"}:
        return "localhost"
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
    if provider == "localhost":
        if thinking is False or value == "none":
            return "none"
        if value in LOCALHOST_REASONING_EFFORTS:
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
    if provider == "localhost":
        return mode != "none"
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
    if provider == "localhost":
        if mode == "none":
            return "none"
        if mode in LOCALHOST_REASONING_EFFORTS:
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


def _as_optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _as_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
