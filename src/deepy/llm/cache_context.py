from __future__ import annotations

import contextlib
import contextvars
import hashlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

from deepy.config import Settings
from deepy.usage import TokenUsage, normalize_usage
from deepy.utils import json as json_utils


@dataclass(frozen=True)
class CachePrefixSnapshot:
    provider: str
    model: str
    base_url_host: str
    reasoning_mode: str
    model_settings: dict[str, Any]
    system_instructions: str
    tools: tuple[dict[str, Any], ...] = ()
    mcp_tools: tuple[dict[str, Any], ...] = ()
    skill_names: tuple[str, ...] = ()
    runtime_context_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


@dataclass(frozen=True)
class CacheContextState:
    prefix_fingerprint: str | None = None
    prefix_generation: int = 0
    cache_break_reason: str | None = None
    cache_usage: dict[str, Any] | None = None

    @property
    def cache_hit_ratio(self) -> float | None:
        if not isinstance(self.cache_usage, dict):
            return None
        hit_tokens = _int_field(self.cache_usage.get("hit_tokens"))
        miss_tokens = _int_field(self.cache_usage.get("miss_tokens"))
        total = hit_tokens + miss_tokens
        return hit_tokens / total if total else None


@dataclass(frozen=True)
class CachePrefixDiagnostic:
    prefix_snapshot: dict[str, Any] | None
    sdk_request_shape: dict[str, Any]


_diagnostic_sink: contextvars.ContextVar[Callable[[CachePrefixDiagnostic], None] | None] = (
    contextvars.ContextVar("deepy_cache_prefix_diagnostic_sink", default=None)
)
_current_prefix_snapshot: contextvars.ContextVar[CachePrefixSnapshot | None] = contextvars.ContextVar(
    "deepy_current_cache_prefix_snapshot",
    default=None,
)


@contextlib.contextmanager
def capture_cache_prefix_diagnostics(
    sink: Callable[[CachePrefixDiagnostic], None],
) -> Iterator[None]:
    token = _diagnostic_sink.set(sink)
    try:
        yield
    finally:
        _diagnostic_sink.reset(token)


def set_current_cache_prefix_snapshot(snapshot: CachePrefixSnapshot | None) -> contextvars.Token:
    return _current_prefix_snapshot.set(snapshot)


def reset_current_cache_prefix_snapshot(token: contextvars.Token) -> None:
    _current_prefix_snapshot.reset(token)


def capture_sdk_request_shape(
    *,
    system_instructions: str | None,
    input: Any,
    model: str,
    model_settings: Any,
    tools: Sequence[Any] | None,
    mcp_servers: Sequence[Any] | None,
) -> None:
    sink = _diagnostic_sink.get()
    if sink is None:
        return
    snapshot = _current_prefix_snapshot.get()
    sink(
        CachePrefixDiagnostic(
            prefix_snapshot=snapshot.to_dict() if snapshot is not None else None,
            sdk_request_shape={
                "system_instructions": system_instructions or "",
                "input": _safe_canonical_value(input),
                "model": model,
                "model_settings": canonical_model_settings(model_settings),
                "tools": tuple(canonical_tool(tool) for tool in tools or ()),
                "mcp_servers": tuple(canonical_mcp_server(server) for server in mcp_servers or ()),
            },
        )
    )


def build_cache_prefix_snapshot(
    settings: Settings,
    *,
    system_instructions: str,
    tools: Sequence[Any] = (),
    mcp_servers: Sequence[Any] = (),
    model_settings: Any | None = None,
    skill_names: Sequence[str] = (),
    runtime_context_key: str = "",
) -> CachePrefixSnapshot:
    return CachePrefixSnapshot(
        provider=settings.model.provider,
        model=settings.model.name,
        base_url_host=_base_url_host(settings.model.base_url),
        reasoning_mode=settings.model.reasoning_mode,
        model_settings=canonical_model_settings(model_settings),
        system_instructions=system_instructions,
        tools=tuple(canonical_tool(tool) for tool in tools),
        mcp_tools=tuple(canonical_mcp_server(server) for server in mcp_servers),
        skill_names=tuple(sorted(str(name) for name in skill_names if str(name))),
        runtime_context_key=runtime_context_key,
    )


def cache_break_reason_for_snapshot_change(
    previous: CachePrefixSnapshot,
    current: CachePrefixSnapshot,
) -> str:
    previous_dict = previous.to_dict()
    current_dict = current.to_dict()
    for key in (
        "provider",
        "model",
        "base_url_host",
        "reasoning_mode",
        "model_settings",
        "system_instructions",
        "tools",
        "mcp_tools",
        "skill_names",
        "runtime_context_key",
    ):
        if previous_dict.get(key) != current_dict.get(key):
            return f"prefix changed: {key}"
    return "prefix changed"


def build_cache_usage_update(
    previous: Mapping[str, Any] | None,
    usage: TokenUsage | Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized = usage if isinstance(usage, TokenUsage) else normalize_usage(usage)
    payload = dict(previous or {})
    hit_tokens = _int_field(payload.get("hit_tokens"))
    miss_tokens = _int_field(payload.get("miss_tokens"))
    known_turns = _int_field(payload.get("known_turns"))
    unknown_turns = _int_field(payload.get("unknown_turns"))

    cache_tokens = normalized.prompt_cache_hit_tokens + normalized.prompt_cache_miss_tokens
    if normalized.known and cache_tokens:
        hit_tokens += normalized.prompt_cache_hit_tokens
        miss_tokens += normalized.prompt_cache_miss_tokens
        known_turns += 1
        payload["last_hit_tokens"] = normalized.prompt_cache_hit_tokens
        payload["last_miss_tokens"] = normalized.prompt_cache_miss_tokens
        payload["last_hit_ratio"] = normalized.prompt_cache_hit_tokens / cache_tokens
    elif normalized.known:
        unknown_turns += 1
        payload["last_hit_tokens"] = None
        payload["last_miss_tokens"] = None
        payload["last_hit_ratio"] = None

    payload["hit_tokens"] = hit_tokens
    payload["miss_tokens"] = miss_tokens
    payload["known_turns"] = known_turns
    payload["unknown_turns"] = unknown_turns
    total = hit_tokens + miss_tokens
    payload["hit_ratio"] = hit_tokens / total if total else None
    return payload


def format_cache_usage(cache_usage: Mapping[str, Any] | None) -> str:
    if not cache_usage:
        return "unknown"
    hit_tokens = _int_field(cache_usage.get("hit_tokens"))
    miss_tokens = _int_field(cache_usage.get("miss_tokens"))
    total = hit_tokens + miss_tokens
    if not total:
        return "unknown"
    return (
        f"fresh input {miss_tokens:,} · cached input {hit_tokens:,} "
        f"({hit_tokens / total * 100:.1f}% hit)"
    )


def format_cache_hit_rate(cache_usage: Mapping[str, Any] | None) -> str:
    if not cache_usage:
        return "unknown"
    hit_tokens = _int_field(cache_usage.get("hit_tokens"))
    miss_tokens = _int_field(cache_usage.get("miss_tokens"))
    total = hit_tokens + miss_tokens
    if not total:
        return "unknown"
    return f"{hit_tokens / total * 100:.0f}%"


def canonical_model_settings(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump") and callable(value.model_dump):
        raw = value.model_dump(exclude_none=True)
    elif hasattr(value, "__dict__"):
        raw = dict(value.__dict__)
    elif isinstance(value, Mapping):
        raw = dict(value)
    else:
        raw = {"value": str(value)}
    return _safe_canonical_value(raw)


def canonical_tool(tool: Any) -> dict[str, Any]:
    raw = _safe_canonical_value(tool)
    if isinstance(raw, dict):
        return {
            "name": _first_string(
                raw.get("name"),
                raw.get("tool_name"),
                _nested(raw, "function_schema", "name"),
                _nested(raw, "schema", "name"),
            ),
            "description": _first_string(
                raw.get("description"),
                _nested(raw, "function_schema", "description"),
                _nested(raw, "schema", "description"),
            ),
            "schema": _safe_canonical_value(
                raw.get("params_json_schema")
                or raw.get("parameters")
                or _nested(raw, "function_schema", "params_json_schema")
                or _nested(raw, "schema", "parameters")
                or raw
            ),
        }
    return {"name": str(raw), "description": "", "schema": raw}


def canonical_mcp_server(server: Any) -> dict[str, Any]:
    tools = getattr(server, "cached_tools", None)
    if tools is None:
        tools = getattr(server, "tools", None)
    return {
        "name": str(getattr(server, "name", "mcp")),
        "tools": tuple(canonical_tool(tool) for tool in tools or ()),
    }


def _base_url_host(base_url: str) -> str:
    parsed = urlparse(base_url)
    return (parsed.hostname or base_url).rstrip("/").lower()


def _canonical_json(value: Any) -> str:
    return json_utils.dumps(_safe_canonical_value(value))


def _safe_canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _safe_canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).lower() not in {"api_key", "authorization", "headers", "extra_headers"}
        }
    if isinstance(value, tuple | list):
        return tuple(_safe_canonical_value(item) for item in value)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _safe_canonical_value(value.model_dump(exclude_none=True))
    if hasattr(value, "__dict__"):
        public = {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_") and key.lower() not in {"api_key", "authorization"}
        }
        return _safe_canonical_value(public)
    return str(value)


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _first_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return ""


def _int_field(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float) and value.is_integer():
        return max(int(value), 0)
    return 0
