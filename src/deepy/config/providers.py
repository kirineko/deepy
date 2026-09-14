from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

DEFAULT_MODEL = "deepseek-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_000_000
DEFAULT_COMPACT_TRIGGER_RATIO = 0.8
DEFAULT_RESERVED_CONTEXT_TOKENS = 50_000
DEFAULT_COMPACT_PRESERVE_RECENT_MESSAGES = 2
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
DEFAULT_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_CLI_PROXY_BASE_URL = "http://127.0.0.1:8317/v1"
DEEPSEEK_REASONING_EFFORTS = {"high", "max"}
SWITCH_ONLY_REASONING_EFFORTS = {"enabled", "none"}
CLI_PROXY_REASONING_MODES = ("none", "low", "medium", "high", "xhigh")
CLI_PROXY_REASONING_EFFORTS = set(CLI_PROXY_REASONING_MODES)
KIMI_REASONING_MODES = ("low", "high", "max")
DEEPSEEK_REASONING_MODES = ("none", "high", "max")
SWITCH_ONLY_THINKING_MODES = ("disabled", "enabled")
REASONING_MODES = set(DEEPSEEK_REASONING_MODES)
THINKING_MODES = set(
    DEEPSEEK_REASONING_MODES
    + SWITCH_ONLY_THINKING_MODES
    + CLI_PROXY_REASONING_MODES
    + KIMI_REASONING_MODES
)
REASONING_EFFORTS = THINKING_MODES
PROVIDERS = {"deepseek", "mimo", "kimi", "cli_proxy"}
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
    api: str = PROVIDER_API_RESPONSES
    api_key_url: str | None = None


DeepSeekModelInfo = ModelInfo


DEEPSEEK_MODEL_CATALOG = (
    ModelInfo(
        "deepseek-flash",
        "DeepSeek V4.1 Flash",
        "DeepSeek Flash Responses with image input.",
        supports_image_input=True,
    ),
)
MIMO_MODEL_CATALOG = (
    ModelInfo(
        "mimo-v2.5",
        "MiMo 2.5",
        "MiMo Responses with image input.",
        supports_image_input=True,
        default_reasoning_mode="enabled",
    ),
    ModelInfo(
        "mimo-v2.5-pro",
        "MiMo 2.5 Pro",
        "MiMo Pro text reasoning.",
        default_reasoning_mode="enabled",
    ),
)
KIMI_MODEL_CATALOG = (
    ModelInfo("kimi-k3", "Kimi K3", "Kimi Responses with image input.", supports_image_input=True),
)
CLI_PROXY_MODEL_CATALOG = tuple(
    ModelInfo(
        name,
        label,
        "CLI Proxy Responses with image input.",
        supports_image_input=True,
        default_reasoning_mode="medium",
    )
    for name, label in (
        ("gpt-6-astra", "GPT-6 Astra"),
        ("gpt-5.6-sol", "GPT-5.6 Sol"),
        ("gpt-5.6-terra", "GPT-5.6 Terra"),
        ("gpt-5.6-luna", "GPT-5.6 Luna"),
        ("gpt-5.5", "GPT-5.5"),
    )
)
PROVIDER_CATALOG = (
    ProviderInfo(
        "deepseek",
        "DeepSeek",
        "DeepSeek official Responses API.",
        DEFAULT_BASE_URL,
        DEEPSEEK_MODEL_CATALOG,
        DEEPSEEK_REASONING_MODES,
        DEFAULT_MODEL,
        "max",
        api_key_url="https://platform.deepseek.com/api_keys",
    ),
    ProviderInfo(
        "mimo",
        "MiMo",
        "Xiaomi MiMo Responses API.",
        DEFAULT_MIMO_BASE_URL,
        MIMO_MODEL_CATALOG,
        SWITCH_ONLY_THINKING_MODES,
        "mimo-v2.5",
        "enabled",
        api_key_url="https://platform.xiaomimimo.com/console/api-keys",
    ),
    ProviderInfo(
        "kimi",
        "Kimi",
        "Kimi Responses API.",
        "https://api.moonshot.cn/v1",
        KIMI_MODEL_CATALOG,
        KIMI_REASONING_MODES,
        "kimi-k3",
        "max",
        api_key_url="https://platform.moonshot.cn/console/api-keys",
    ),
    ProviderInfo(
        "cli_proxy",
        "CLI Proxy",
        "Local CLI Proxy Responses API.",
        DEFAULT_CLI_PROXY_BASE_URL,
        CLI_PROXY_MODEL_CATALOG,
        CLI_PROXY_REASONING_MODES,
        "gpt-5.6-terra",
        "medium",
    ),
)
PROVIDER_BY_ID = {provider.id: provider for provider in PROVIDER_CATALOG}
SUPPORTED_DEEPSEEK_MODELS = frozenset(model.name for model in DEEPSEEK_MODEL_CATALOG)
SUPPORTED_MODELS_BY_PROVIDER = {
    provider.id: frozenset(model.name for model in provider.models) for provider in PROVIDER_CATALOG
}


def provider_info_for(provider: str | None) -> ProviderInfo:
    key = provider or DEFAULT_PROVIDER
    if key not in PROVIDER_BY_ID:
        raise ValueError(f"Unsupported provider: {key}. Choose deepseek, mimo, kimi, or cli_proxy.")
    return PROVIDER_BY_ID[key]


def resolve_provider(raw_provider: str | None, base_url: str | None) -> str:
    return provider_info_for((raw_provider or DEFAULT_PROVIDER).strip().lower()).id


def infer_provider_from_base_url(base_url: str | None) -> str | None:
    """Identify endpoints for diagnostics, never for configuration selection."""
    host = (urlparse(base_url or "").hostname or "").lower()
    return {
        "api.deepseek.com": "deepseek",
        "api.xiaomimimo.com": "mimo",
        "api.moonshot.cn": "kimi",
        "127.0.0.1": "cli_proxy",
        "localhost": "cli_proxy",
    }.get(host)


def _raw_provider_value(raw: Mapping[str, Any], env: Mapping[str, str]) -> str | None:
    provider = _as_str(env.get("DEEPY_PROVIDER"), _as_str(raw.get("provider"), ""))
    return provider.lower() if provider else None


def is_supported_provider(value: str) -> bool:
    return value in PROVIDERS


def is_supported_model_for_provider(model: str, provider: str) -> bool:
    return model in SUPPORTED_MODELS_BY_PROVIDER.get(provider, ())


def allows_custom_model_for_provider(provider: str) -> bool:
    return False


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


def normalize_reasoning_effort(value: str, *, provider: str, thinking: bool | None) -> str:
    mode = value
    if thinking is False:
        mode = "disabled" if provider == "mimo" else "none"
    if provider == "mimo" and mode == "none":
        mode = "disabled"
    if not is_valid_thinking_mode_for_provider(mode, provider):
        raise ValueError(f"Unsupported reasoning mode {mode} for {provider}.")
    return reasoning_effort_for_mode(mode, provider)


def thinking_enabled_for_mode(mode: str, provider: str) -> bool:
    return mode not in {"none", "disabled"}


def reasoning_effort_for_mode(mode: str, provider: str) -> str:
    return "none" if mode == "disabled" else mode


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
