from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Self

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_048_576
DEFAULT_COMPACT_TRIGGER_RATIO = 0.8
DEFAULT_COMPACT_PROMPT_TOKEN_THRESHOLD = 838_861
REASONING_EFFORTS = {"high", "max"}


def default_config_path() -> Path:
    return Path.home() / ".deepy" / "config.toml"


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
        name = _as_str(raw.get("name"), env.get("DEEPY_MODEL", DEFAULT_MODEL))
        base_url = _as_str(raw.get("base_url"), env.get("DEEPY_BASE_URL", DEFAULT_BASE_URL))
        api_key = _as_str(raw.get("api_key"), env.get("DEEPY_API_KEY", "")) or None
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
        return self.name in {"deepseek-v4-pro", "deepseek-v4-flash"}


@dataclass(frozen=True)
class ContextConfig:
    window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    compact_trigger_ratio: float = DEFAULT_COMPACT_TRIGGER_RATIO
    compact_prompt_token_threshold: int | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        window_tokens = _as_int(raw.get("window_tokens"), DEFAULT_CONTEXT_WINDOW_TOKENS)
        ratio = _as_float(raw.get("compact_trigger_ratio"), DEFAULT_COMPACT_TRIGGER_RATIO)
        if ratio <= 0 or ratio > 1:
            ratio = DEFAULT_COMPACT_TRIGGER_RATIO
        threshold = raw.get("compact_prompt_token_threshold")
        compact_threshold = _as_int(threshold, 0) if threshold is not None else None
        return cls(
            window_tokens=window_tokens,
            compact_trigger_ratio=ratio,
            compact_prompt_token_threshold=compact_threshold or None,
        )

    @property
    def resolved_compact_threshold(self) -> int:
        if self.compact_prompt_token_threshold:
            return self.compact_prompt_token_threshold
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
    command: str | None = None
    api_url: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            command=_as_str(raw.get("command")) or None,
            api_url=_as_str(raw.get("api_url")) or None,
        )


@dataclass(frozen=True)
class ToolsConfig:
    web_search: WebSearchToolConfig = field(default_factory=WebSearchToolConfig)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Self:
        return cls(web_search=WebSearchToolConfig.from_mapping(_as_mapping(raw.get("web_search"))))


@dataclass(frozen=True)
class Settings:
    model: ModelConfig = field(default_factory=ModelConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
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
    api_key = settings.model.api_key
    if api_key:
        data["model"]["api_key"] = api_key if reveal_secret else mask_secret(api_key)
    data["model"]["thinking"] = settings.model.thinking_enabled
    data["context"]["compact_prompt_token_threshold"] = (
        settings.context.resolved_compact_threshold
    )
    return _drop_empty(data)


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
