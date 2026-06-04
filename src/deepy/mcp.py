from __future__ import annotations

import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager, contextmanager, suppress
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from deepy.audit import AuditPolicy
from deepy.config import Settings, default_mcp_config_path, mask_secret
from deepy.utils import json as json_utils

MCP_SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ENV_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
WEB_SEARCH_HINTS = ("tavily", "search", "web_search", "web-search")
MCP_TOOL_NAME_MAX_LENGTH = 64
MCP_TOOL_NAME_HASH_LENGTH = 8


McpTransport = Literal["stdio", "streamable_http"]
McpServerState = Literal["configured", "active", "failed", "invalid", "disabled"]


@dataclass(frozen=True)
class McpServerDefinition:
    name: str
    transport: McpTransport
    source: str
    enabled: bool = True
    command: str | None = None
    args: tuple[str, ...] = ()
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    roles: tuple[str, ...] = ()
    preferred_tools: tuple[str, ...] = ()
    validation_error: str | None = None

    @property
    def valid(self) -> bool:
        return self.validation_error is None and self.enabled

    @property
    def web_search_role(self) -> bool:
        return "web_search" in {role.lower() for role in self.roles}


@dataclass(frozen=True)
class McpToolInfo:
    server_name: str
    original_name: str
    model_name: str
    description: str = ""
    preferred_web_search: bool = False


@dataclass(frozen=True)
class McpServerStatus:
    name: str
    transport: str
    source: str
    state: McpServerState
    error: str | None = None
    tool_count: int = 0
    tools: tuple[str, ...] = ()
    preferred_web_search_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class McpConfigLoadResult:
    definitions: tuple[McpServerDefinition, ...]
    errors: tuple[McpServerStatus, ...] = ()


class DeepyMcpRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        project_root: Path | None = None,
        env: Mapping[str, str] | None = None,
        audit_policy: AuditPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.project_root = project_root
        self.audit_policy = audit_policy or AuditPolicy.from_mode(settings.audit.mode, settings.audit)
        self.load_result = load_mcp_config(settings, project_root=project_root, env=env)
        self.definitions = self.load_result.definitions
        self._servers_by_name: dict[str, Any] = {}
        self._definitions_by_server: dict[Any, McpServerDefinition] = {}
        self._manager: Any | None = None
        self._statuses: dict[str, McpServerStatus] = {
            status.name: status for status in self.load_result.errors
        }
        self.tools: list[McpToolInfo] = []
        self.connected = False
        self._shutting_down = False
        self._connect_lock = asyncio.Lock()
        self._connect_task: asyncio.Task[None] | None = None

    @property
    def active_servers(self) -> list[Any]:
        if self._manager is None:
            return []
        return list(self._manager.active_servers)

    @property
    def preferred_web_search_tools(self) -> list[str]:
        return [tool.model_name for tool in self.tools if tool.preferred_web_search]

    @property
    def statuses(self) -> list[McpServerStatus]:
        ordered: list[McpServerStatus] = []
        for definition in self.definitions:
            status = self._statuses.get(definition.name)
            if status is not None:
                ordered.append(status)
        for status in self.load_result.errors:
            if status.name not in {item.name for item in ordered}:
                ordered.append(status)
        return ordered

    async def connect(self) -> None:
        if self.connected:
            return
        async with self._connect_lock:
            if self.connected:
                return
            if self._connect_task is None:
                self._connect_task = asyncio.create_task(self._connect_once())
            task = self._connect_task
        try:
            await task
        except asyncio.CancelledError:
            await self._await_connect_task(task)
            if not self._shutting_down:
                await self._release_manager()
            raise
        finally:
            async with self._connect_lock:
                if self._connect_task is task and task.done():
                    self._connect_task = None
        if self._shutting_down:
            await self._release_manager()
            return

    async def _await_connect_task(self, task: asyncio.Task[None]) -> None:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _connect_once(self) -> None:
        if self._shutting_down:
            return
        if not self.settings.mcp.enabled:
            self.connected = True
            return
        try:
            servers = self._build_sdk_servers()
        except Exception as exc:
            self._record_connect_failure(exc)
            return
        if not servers:
            self.connected = True
            return
        try:
            from agents.mcp import MCPServerManager

            self._manager = MCPServerManager(
                servers,
                connect_timeout_seconds=self.settings.mcp.connect_timeout_seconds,
                cleanup_timeout_seconds=self.settings.mcp.cleanup_timeout_seconds,
                drop_failed_servers=True,
                strict=False,
            )
            await self._manager.connect_all()
            if self._shutting_down:
                await self._release_manager()
                return
            self._record_manager_failures()
            await self._collect_active_tools()
            self.connected = True
        except asyncio.CancelledError:
            if not self._shutting_down:
                await self._release_manager()
            raise
        except Exception as exc:
            self._record_connect_failure(exc)
            await self._release_manager()

    async def _release_manager(self) -> None:
        manager = self._manager
        self._manager = None
        self.connected = False
        if manager is not None:
            with suppress(asyncio.CancelledError, Exception):
                await manager.cleanup_all()

    async def shutdown(self) -> None:
        """Cancel an in-flight connect and release MCP resources."""
        with _quiet_mcp_teardown_logs():
            self._shutting_down = True
            task: asyncio.Task[None] | None
            async with self._connect_lock:
                task = self._connect_task
            if task is not None:
                await self._await_connect_task(task)
            async with self._connect_lock:
                if self._connect_task is task:
                    self._connect_task = None
            await self._release_manager()

    async def cleanup(self) -> None:
        await self.shutdown()

    def _build_sdk_servers(self) -> list[Any]:
        from agents.mcp import (
            MCPServerStdioParams,
            MCPServerStreamableHttp,
            MCPServerStreamableHttpParams,
        )

        servers: list[Any] = []
        for definition in self.definitions:
            if not definition.enabled:
                self._statuses[definition.name] = _status_from_definition(
                    definition,
                    "disabled",
                )
                continue
            if definition.validation_error:
                self._statuses[definition.name] = _status_from_definition(
                    definition,
                    "invalid",
                    error=definition.validation_error,
                )
                continue
            if definition.transport == "stdio":
                params: MCPServerStdioParams = {"command": definition.command or ""}
                if definition.args:
                    params["args"] = list(definition.args)
                if definition.env:
                    params["env"] = dict(definition.env)
                if definition.cwd:
                    params["cwd"] = definition.cwd
                server = _quiet_stdio_server(
                    params=params,
                    name=definition.name,
                    cache_tools_list=self.settings.mcp.cache_tools_list,
                    client_session_timeout_seconds=(
                        self.settings.mcp.client_session_timeout_seconds
                    ),
                    require_approval=self._mcp_require_approval(definition),
                )
            else:
                params: MCPServerStreamableHttpParams = {"url": definition.url or ""}
                if definition.headers:
                    params["headers"] = dict(definition.headers)
                server = MCPServerStreamableHttp(
                    params=params,
                    name=definition.name,
                    cache_tools_list=self.settings.mcp.cache_tools_list,
                    client_session_timeout_seconds=(
                        self.settings.mcp.client_session_timeout_seconds
                    ),
                    require_approval=self._mcp_require_approval(definition),
                )
            self._servers_by_name[definition.name] = server
            self._definitions_by_server[server] = definition
            self._statuses[definition.name] = _status_from_definition(definition, "configured")
            servers.append(server)
        return servers

    def _mcp_require_approval(self, definition: McpServerDefinition):
        async def needs_approval(_context: object, _agent: object, tool: object) -> bool:
            tool_name = str(getattr(tool, "name", "") or "")
            return self.audit_policy.needs_mcp_approval(server=definition.name, tool=tool_name)

        return needs_approval

    def _record_manager_failures(self) -> None:
        if self._manager is None:
            return
        for server, error in self._manager.errors.items():
            definition = self._definitions_by_server.get(server)
            if definition is None:
                continue
            self._statuses[definition.name] = _status_from_definition(
                definition,
                "failed",
                error=str(error),
            )

    def _record_connect_failure(self, exc: Exception) -> None:
        for definition in self.definitions:
            status = self._statuses.get(definition.name)
            if status is not None and status.state in {"disabled", "invalid"}:
                continue
            self._statuses[definition.name] = _status_from_definition(
                definition,
                "failed",
                error=str(exc),
            )

    async def _collect_active_tools(self) -> None:
        if self._manager is None:
            return
        active_set = set(self._manager.active_servers)
        tools: list[McpToolInfo] = []
        for server in self._manager.active_servers:
            definition = self._definitions_by_server.get(server)
            if definition is None:
                continue
            try:
                listed = await server.list_tools()
            except Exception as exc:
                self._statuses[definition.name] = _status_from_definition(
                    definition,
                    "failed",
                    error=str(exc),
                )
                continue
            server_tool_names: list[str] = []
            preferred: list[str] = []
            for tool in listed:
                original_name = str(getattr(tool, "name", ""))
                description = str(getattr(tool, "description", "") or "")
                model_name = sdk_mcp_tool_name(definition.name, original_name)
                is_preferred = is_preferred_web_search_tool(
                    definition,
                    original_name,
                    description,
                    self.settings,
                )
                tools.append(
                    McpToolInfo(
                        server_name=definition.name,
                        original_name=original_name,
                        model_name=model_name,
                        description=description,
                        preferred_web_search=is_preferred,
                    )
                )
                server_tool_names.append(model_name)
                if is_preferred:
                    preferred.append(model_name)
            self._statuses[definition.name] = _status_from_definition(
                definition,
                "active" if server in active_set else "failed",
                tool_count=len(server_tool_names),
                tools=tuple(server_tool_names),
                preferred_web_search_tools=tuple(preferred),
            )
        self.tools = tools


async def teardown_mcp_after_startup(
    mcp_runtime: DeepyMcpRuntime,
    startup_future: Future[Any],
) -> None:
    """Cancel startup connect on the active loop, then release MCP resources."""
    if not startup_future.done():
        startup_future.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await asyncio.wrap_future(startup_future)
    await asyncio.sleep(0)
    await mcp_runtime.cleanup()


@contextmanager
def _quiet_mcp_teardown_logs():
    loggers = (
        logging.getLogger("openai.agents"),
        logging.getLogger("agents"),
    )
    previous_levels = [(logger, logger.level) for logger in loggers]
    for logger, _ in previous_levels:
        logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        for logger, level in previous_levels:
            logger.setLevel(level)


def load_mcp_config(
    settings: Settings,
    *,
    project_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> McpConfigLoadResult:
    if not settings.mcp.enabled:
        return McpConfigLoadResult(())

    env = env or os.environ
    definitions: list[McpServerDefinition] = []
    errors: list[McpServerStatus] = []
    if settings.path is not None:
        global_path = default_mcp_config_path(settings.path)
        _load_mcp_file(global_path, "global", definitions, errors, env)

    if settings.mcp.allow_project_config and project_root is not None:
        project_path = project_root.resolve() / ".deepy" / "mcp.json"
        _load_mcp_file(project_path, "project", definitions, errors, env)

    return McpConfigLoadResult(tuple(definitions), tuple(errors))


def format_mcp_status(statuses: list[McpServerStatus]) -> str:
    if not statuses:
        return "MCP: no servers configured."

    lines = ["MCP servers:"]
    for status in statuses:
        suffix = f" ({status.error})" if status.error else ""
        lines.append(
            f"- {status.name} ({status.state}) {status.transport}, "
            f"tools={status.tool_count}, source={status.source}{suffix}"
        )
        for tool in status.tools:
            marker = " *web-search*" if tool in status.preferred_web_search_tools else ""
            lines.append(f"  - {tool}{marker}")
    return "\n".join(lines)


def mcp_policy_to_dict(settings: Settings) -> dict[str, Any]:
    return {
        "enabled": settings.mcp.enabled,
        "config_path": str(default_mcp_config_path(settings.path)),
        "connect_timeout_seconds": settings.mcp.connect_timeout_seconds,
        "cleanup_timeout_seconds": settings.mcp.cleanup_timeout_seconds,
        "client_session_timeout_seconds": settings.mcp.client_session_timeout_seconds,
        "cache_tools_list": settings.mcp.cache_tools_list,
        "allow_project_config": settings.mcp.allow_project_config,
        "prefer_mcp_web_search": settings.mcp.prefer_mcp_web_search,
        "web_search": {
            "prefer_mcp": settings.mcp.web_search.prefer_mcp,
            "preferred_server": settings.mcp.web_search.preferred_server,
            "preferred_tools": list(settings.mcp.web_search.preferred_tools),
            "fallback_to_builtin": settings.mcp.web_search.fallback_to_builtin,
        },
    }


def mask_mapping_secrets(values: Mapping[str, str]) -> dict[str, str]:
    return {key: mask_secret(value) for key, value in values.items()}


def sdk_mcp_tool_name(server_name: str, tool_name: str) -> str:
    server_part = _safe_tool_name_part(server_name, "server")
    tool_part = _safe_tool_name_part(tool_name, "tool")
    base_name = f"mcp_{server_part}__{tool_part}"
    if len(base_name) <= MCP_TOOL_NAME_MAX_LENGTH:
        return base_name

    import hashlib

    hash_suffix = hashlib.sha1(f"{server_name}\0{tool_name}".encode("utf-8")).hexdigest()[
        :MCP_TOOL_NAME_HASH_LENGTH
    ]
    suffix = f"_{hash_suffix}"
    stem_length = MCP_TOOL_NAME_MAX_LENGTH - len(suffix)
    stem = base_name[:stem_length].rstrip("_-") or "mcp"
    return f"{stem}{suffix}"


def _safe_tool_name_part(value: str, fallback: str) -> str:
    safe = "".join(
        char if char.isascii() and (char.isalnum() or char in {"_", "-"}) else "_"
        for char in value
    )
    safe = safe.strip("_-")
    return safe or fallback


def is_preferred_web_search_tool(
    definition: McpServerDefinition,
    tool_name: str,
    description: str = "",
    settings: Settings | None = None,
) -> bool:
    if settings is not None:
        preferred_server = settings.mcp.web_search.preferred_server
        preferred_tools = {tool.lower() for tool in settings.mcp.web_search.preferred_tools}
        if preferred_server and definition.name.lower() == preferred_server.lower():
            if not preferred_tools or tool_name.lower() in preferred_tools:
                return True
        if tool_name.lower() in preferred_tools:
            return True

    haystack = " ".join(
        [definition.name, tool_name, description, *definition.roles, *definition.preferred_tools]
    ).lower()
    return definition.web_search_role or any(hint in haystack for hint in WEB_SEARCH_HINTS)


def _status_from_definition(
    definition: McpServerDefinition,
    state: McpServerState,
    *,
    error: str | None = None,
    tool_count: int = 0,
    tools: tuple[str, ...] = (),
    preferred_web_search_tools: tuple[str, ...] = (),
) -> McpServerStatus:
    return McpServerStatus(
        name=definition.name,
        transport=definition.transport,
        source=definition.source,
        state=state,
        error=error,
        tool_count=tool_count,
        tools=tools,
        preferred_web_search_tools=preferred_web_search_tools,
    )


def _quiet_stdio_server(**kwargs: Any) -> Any:
    from agents.mcp import MCPServerStdio

    class DeepyQuietMCPServerStdio(MCPServerStdio):
        def create_streams(self) -> Any:
            return _quiet_stdio_client(self.params)

    return DeepyQuietMCPServerStdio(**kwargs)


@asynccontextmanager
async def _quiet_stdio_client(params: Any):
    from mcp import stdio_client

    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as streams:
            yield streams


def _load_mcp_file(
    path: Path,
    source: str,
    definitions: list[McpServerDefinition],
    errors: list[McpServerStatus],
    env: Mapping[str, str],
) -> None:
    if not path.exists():
        return
    try:
        raw = json_utils.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(
            McpServerStatus(
                name=str(path),
                transport="unknown",
                source=source,
                state="invalid",
                error=f"invalid JSON: {exc}",
            )
        )
        return
    servers = raw.get("mcpServers") if isinstance(raw, Mapping) else None
    if not isinstance(servers, Mapping):
        errors.append(
            McpServerStatus(
                name=str(path),
                transport="unknown",
                source=source,
                state="invalid",
                error="missing mcpServers object",
            )
        )
        return
    for name, value in servers.items():
        if not isinstance(name, str) or not isinstance(value, Mapping):
            errors.append(
                McpServerStatus(
                    name=str(name),
                    transport="unknown",
                    source=source,
                    state="invalid",
                    error="server definition must be an object",
                )
            )
            continue
        definitions.append(_parse_server_definition(name, value, source, env))


def _parse_server_definition(
    name: str,
    raw: Mapping[str, Any],
    source: str,
    env: Mapping[str, str],
) -> McpServerDefinition:
    enabled = _as_bool(raw.get("enabled"), True)
    transport = _as_str(raw.get("transport"))
    command = _as_str(raw.get("command")) or None
    url = _as_str(raw.get("url")) or None
    if not transport:
        transport = "stdio" if command else "streamable_http"

    validation_error = _validate_common(name, transport)
    if transport == "http":
        transport = "streamable_http"

    args = _as_str_tuple(raw.get("args"))
    roles = _as_str_tuple(raw.get("roles"))
    preferred_tools = _as_str_tuple(raw.get("preferred_tools"))
    cwd = _as_str(raw.get("cwd")) or None
    resolved_env, env_error = _resolve_secret_mapping(raw.get("env"), env)
    headers, header_error = _resolve_secret_mapping(raw.get("headers"), env)
    validation_error = validation_error or env_error or header_error

    if enabled and validation_error is None:
        if transport == "stdio" and not command:
            validation_error = "stdio server requires command"
        elif transport == "streamable_http" and not url:
            validation_error = "streamable_http server requires url"
        elif transport not in {"stdio", "streamable_http"}:
            validation_error = f"unsupported transport: {transport}"

    normalized_transport: McpTransport = (
        "streamable_http" if transport == "streamable_http" else "stdio"
    )
    return McpServerDefinition(
        name=name,
        transport=normalized_transport,
        source=source,
        enabled=enabled,
        command=command,
        args=args,
        cwd=cwd,
        env=resolved_env,
        url=url,
        headers=headers,
        roles=roles,
        preferred_tools=preferred_tools,
        validation_error=validation_error,
    )


def _validate_common(name: str, transport: str) -> str | None:
    if not name.strip():
        return "server name is empty"
    if not MCP_SERVER_NAME_RE.match(name):
        return "server name must contain only letters, numbers, dot, underscore, or dash"
    if transport not in {"stdio", "streamable_http", "http"}:
        return f"unsupported transport: {transport}"
    return None


def _resolve_secret_mapping(value: Any, env: Mapping[str, str]) -> tuple[dict[str, str], str | None]:
    if value is None:
        return {}, None
    if not isinstance(value, Mapping):
        return {}, "env and headers must be objects"
    resolved: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return {}, "env and headers keys and values must be strings"
        match = ENV_PLACEHOLDER_RE.match(item)
        if match is not None:
            env_name = match.group(1)
            env_value = env.get(env_name)
            if env_value is None:
                return {}, f"environment variable {env_name} is not set"
            resolved[key] = env_value
        else:
            resolved[key] = item
    return resolved, None


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
