from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from deepy.audit import AuditConfig, AuditMode, McpSafeTool
from deepy.config import McpConfig, Settings
from deepy.mcp import (
    DeepyMcpRuntime,
    McpServerStatus,
    McpToolInfo,
    format_mcp_status,
    load_mcp_config,
    sdk_mcp_tool_name,
)


def test_load_mcp_config_reads_global_stdio_server(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text("[mcp]\nenabled = true\n", encoding="utf-8")
    mcp_json = tmp_path / "mcp.json"
    mcp_json.write_text(
        """
{
  "mcpServers": {
    "tavily": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "tavily-mcp"],
      "env": {"TAVILY_API_KEY": "${TAVILY_API_KEY}"},
      "roles": ["web_search"]
    }
  }
}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-secret")

    result = load_mcp_config(Settings(path=config))

    assert result.errors == ()
    assert len(result.definitions) == 1
    server = result.definitions[0]
    assert server.name == "tavily"
    assert server.transport == "stdio"
    assert server.command == "npx"
    assert server.args == ("-y", "tavily-mcp")
    assert server.env == {"TAVILY_API_KEY": "tvly-secret"}
    assert server.roles == ("web_search",)


def test_load_mcp_config_reads_streamable_http_server(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[mcp]\nenabled = true\n", encoding="utf-8")
    (tmp_path / "mcp.json").write_text(
        """
{
  "mcpServers": {
    "remote": {
      "transport": "streamable_http",
      "url": "https://mcp.example/mcp",
      "headers": {"Authorization": "Bearer static-token"}
    }
  }
}
""",
        encoding="utf-8",
    )

    result = load_mcp_config(Settings(path=config))

    assert result.errors == ()
    assert result.definitions[0].transport == "streamable_http"
    assert result.definitions[0].url == "https://mcp.example/mcp"
    assert result.definitions[0].headers == {"Authorization": "Bearer static-token"}


def test_load_mcp_config_missing_file_is_empty(tmp_path):
    result = load_mcp_config(Settings(path=tmp_path / "config.toml"))

    assert result.definitions == ()
    assert result.errors == ()


def test_load_mcp_config_records_invalid_and_unresolved_placeholder(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[mcp]\nenabled = true\n", encoding="utf-8")
    (tmp_path / "mcp.json").write_text(
        """
{
  "mcpServers": {
    "bad": {"transport": "streamable_http"},
    "missing-env": {
      "command": "npx",
      "env": {"TOKEN": "${MISSING_TOKEN}"}
    }
  }
}
""",
        encoding="utf-8",
    )

    result = load_mcp_config(Settings(path=config), env={})

    errors = {definition.name: definition.validation_error for definition in result.definitions}
    assert errors["bad"] == "streamable_http server requires url"
    assert errors["missing-env"] == "environment variable MISSING_TOKEN is not set"


def test_project_mcp_config_is_ignored_by_default(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[mcp]\nenabled = true\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / ".deepy" / "mcp.json"
    project_config.parent.mkdir()
    project_config.write_text(
        '{"mcpServers": {"project-server": {"command": "npx"}}}',
        encoding="utf-8",
    )

    result = load_mcp_config(Settings(path=config), project_root=project)

    assert result.definitions == ()


def test_project_mcp_config_loads_when_explicitly_allowed(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[mcp]\nenabled = true\nallow_project_config = true\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / ".deepy" / "mcp.json"
    project_config.parent.mkdir()
    project_config.write_text(
        '{"mcpServers": {"project-server": {"command": "npx"}}}',
        encoding="utf-8",
    )

    result = load_mcp_config(
        Settings(path=config, mcp=McpConfig(allow_project_config=True)),
        project_root=project,
    )

    assert result.definitions[0].name == "project-server"
    assert result.definitions[0].source == "project"


def test_mcp_runtime_collects_active_tools_and_web_search_preference(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"tavily": {"command": "npx", "roles": ["web_search"]}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    server = _FakeMcpServer("tavily")

    def build_servers():
        definition = runtime.definitions[0]
        runtime._definitions_by_server[server] = definition
        runtime._statuses[definition.name] = McpServerStatus(
            name=definition.name,
            transport=definition.transport,
            source=definition.source,
            state="configured",
        )
        return [server]

    runtime._build_sdk_servers = build_servers  # type: ignore[method-assign]

    asyncio.run(runtime.connect())
    assert runtime.active_servers == [server]
    assert runtime.preferred_web_search_tools == ["mcp_tavily__tavily_search"]
    asyncio.run(runtime.cleanup())

    assert runtime.active_servers == []
    assert runtime.preferred_web_search_tools == []
    assert runtime._definitions_by_server == {}
    assert runtime.statuses[0].state == "active"
    assert runtime.statuses[0].tools == ("mcp_tavily__tavily_search",)
    assert server.cleaned is True


def test_mcp_runtime_stdio_servers_suppress_child_stderr(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"tavily": {"command": "npx", "args": ["-y", "tavily-mcp"]}}}',
        encoding="utf-8",
    )
    captured = {}

    @asynccontextmanager
    async def fake_stdio_client(params, *, errlog):
        captured["command"] = params.command
        captured["errlog"] = errlog
        yield ("read", "write")

    monkeypatch.setattr("mcp.stdio_client", fake_stdio_client)
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    server = runtime._build_sdk_servers()[0]

    async def use_streams():
        async with server.create_streams() as streams:
            assert streams == ("read", "write")
            assert captured["command"] == "npx"
            assert captured["errlog"].name == "/dev/null"
            assert captured["errlog"].closed is False

    asyncio.run(use_streams())

    assert captured["errlog"].closed is True


@pytest.mark.asyncio
async def test_mcp_runtime_uses_audit_require_approval_policy(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"github": {"command": "npx"}}}',
        encoding="utf-8",
    )
    settings = Settings(
        path=config,
        audit=AuditConfig(
            mode=AuditMode.AUTO,
            mcp_safe_tools=(McpSafeTool("github", "search_issues"),),
        ),
    )
    runtime = DeepyMcpRuntime(settings, project_root=tmp_path)
    server = runtime._build_sdk_servers()[0]

    safe = server._get_needs_approval_for_tool(  # noqa: SLF001 - verifies SDK policy wiring.
        SimpleNamespace(name="search_issues"),
        agent=object(),
    )
    unsafe = server._get_needs_approval_for_tool(  # noqa: SLF001 - verifies SDK policy wiring.
        SimpleNamespace(name="create_issue"),
        agent=object(),
    )

    assert await safe(None, {}, "call") is False
    assert await unsafe(None, {}, "call") is True

    runtime.audit_policy.mode_getter = lambda: AuditMode.YOLO
    assert await unsafe(None, {}, "call") is False


def test_sdk_mcp_tool_name_matches_agents_sdk_prefix():
    assert sdk_mcp_tool_name("tavily", "tavily_search") == "mcp_tavily__tavily_search"
    assert sdk_mcp_tool_name("my.server", "tool/name") == "mcp_my_server__tool_name"


def test_mcp_runtime_records_failed_server(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"broken": {"command": "npx"}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    server = _FakeMcpServer("broken", fail_connect=True)

    def build_servers():
        definition = runtime.definitions[0]
        runtime._definitions_by_server[server] = definition
        return [server]

    runtime._build_sdk_servers = build_servers  # type: ignore[method-assign]

    asyncio.run(runtime.connect())

    assert runtime.active_servers == []
    assert runtime.statuses[0].state == "failed"
    assert "connect failed" in (runtime.statuses[0].error or "")


@pytest.mark.asyncio
async def test_mcp_runtime_shutdown_cancels_in_flight_connect(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"tavily": {"command": "npx"}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    gate = asyncio.Event()
    server = _GatedFakeMcpServer("tavily", gate)

    def build_servers():
        definition = runtime.definitions[0]
        runtime._definitions_by_server[server] = definition
        runtime._statuses[definition.name] = McpServerStatus(
            name=definition.name,
            transport=definition.transport,
            source=definition.source,
            state="configured",
        )
        return [server]

    runtime._build_sdk_servers = build_servers  # type: ignore[method-assign]

    connect_task = asyncio.create_task(runtime.connect())
    await asyncio.wait_for(server.entered.wait(), timeout=1.0)
    await runtime.shutdown()
    try:
        await asyncio.wait_for(connect_task, timeout=1.0)
    except asyncio.CancelledError:
        pass

    assert not runtime.connected
    assert runtime.active_servers == []


@pytest.mark.asyncio
async def test_mcp_runtime_connect_waiter_cancel_leaves_shared_task_running(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"tavily": {"command": "npx"}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    gate = asyncio.Event()
    server = _GatedFakeMcpServer("tavily", gate)

    def build_servers():
        definition = runtime.definitions[0]
        runtime._definitions_by_server[server] = definition
        runtime._statuses[definition.name] = McpServerStatus(
            name=definition.name,
            transport=definition.transport,
            source=definition.source,
            state="configured",
        )
        return [server]

    runtime._build_sdk_servers = build_servers  # type: ignore[method-assign]

    primary = asyncio.create_task(runtime.connect())
    await asyncio.wait_for(server.entered.wait(), timeout=1.0)
    secondary = asyncio.create_task(runtime.connect())
    await asyncio.sleep(0)
    secondary.cancel()
    with pytest.raises(asyncio.CancelledError):
        await secondary

    gate.set()
    await asyncio.wait_for(primary, timeout=1.0)

    assert runtime.connected
    assert runtime.active_servers == [server]
    await runtime.cleanup()


@pytest.mark.asyncio
async def test_mcp_runtime_release_clears_server_registry(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"tavily": {"command": "npx"}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    definition = runtime.definitions[0]
    stale_server = object()
    runtime._definitions_by_server[stale_server] = definition
    runtime._servers_by_name["tavily"] = stale_server
    runtime.tools = [
        McpToolInfo(
            server_name="tavily",
            original_name="search",
            model_name="mcp_tavily__search",
        )
    ]

    await runtime._release_manager()

    assert runtime._definitions_by_server == {}
    assert runtime._servers_by_name == {}
    assert runtime.tools == []


@pytest.mark.asyncio
async def test_mcp_runtime_connect_retry_does_not_accumulate_server_references(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"tavily": {"command": "npx"}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    server = _FakeMcpServer("tavily")
    attempts = 0
    original_connect_once = runtime._connect_once

    async def flaky_connect_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            runtime._definitions_by_server[object()] = runtime.definitions[0]
            runtime._definitions_by_server[object()] = runtime.definitions[0]
            await runtime._release_manager()
            raise asyncio.CancelledError()
        await original_connect_once()

    def build_servers_with_name_map():
        definition = runtime.definitions[0]
        runtime._servers_by_name[definition.name] = server
        runtime._definitions_by_server[server] = definition
        runtime._statuses[definition.name] = McpServerStatus(
            name=definition.name,
            transport=definition.transport,
            source=definition.source,
            state="configured",
        )
        return [server]

    runtime._build_sdk_servers = build_servers_with_name_map  # type: ignore[method-assign]
    runtime._connect_once = flaky_connect_once  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await runtime.connect()

    assert runtime._definitions_by_server == {}
    assert runtime._servers_by_name == {}

    await runtime.connect()

    assert len(runtime._definitions_by_server) == 1
    assert len(runtime._servers_by_name) == 1
    await runtime.cleanup()


@pytest.mark.asyncio
async def test_mcp_runtime_connect_retries_after_cancelled_attempt(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"tavily": {"command": "npx"}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)
    server = _FakeMcpServer("tavily")
    attempts = 0
    original_connect_once = runtime._connect_once

    async def flaky_connect_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise asyncio.CancelledError()
        await original_connect_once()

    def build_servers():
        definition = runtime.definitions[0]
        runtime._definitions_by_server[server] = definition
        runtime._statuses[definition.name] = McpServerStatus(
            name=definition.name,
            transport=definition.transport,
            source=definition.source,
            state="configured",
        )
        return [server]

    runtime._build_sdk_servers = build_servers  # type: ignore[method-assign]
    runtime._connect_once = flaky_connect_once  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await runtime.connect()

    assert not runtime.connected
    assert runtime.active_servers == []

    await runtime.connect()

    assert runtime.connected
    assert runtime.active_servers == [server]
    await runtime.cleanup()


def test_mcp_runtime_degrades_when_sdk_setup_raises(tmp_path):
    config = tmp_path / "config.toml"
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers": {"broken": {"command": "npx"}}}',
        encoding="utf-8",
    )
    runtime = DeepyMcpRuntime(Settings(path=config), project_root=tmp_path)

    def build_servers():
        raise RuntimeError("sdk unavailable")

    runtime._build_sdk_servers = build_servers  # type: ignore[method-assign]

    asyncio.run(runtime.connect())

    assert runtime.active_servers == []
    assert runtime.statuses[0].state == "failed"
    assert runtime.statuses[0].error == "sdk unavailable"


def test_format_mcp_status_marks_preferred_search_and_masks_absent_secrets():
    rendered = format_mcp_status(
        [
            McpServerStatus(
                name="tavily",
                transport="stdio",
                source="global",
                state="active",
                tool_count=1,
                tools=("mcp_tavily__tavily_search",),
                preferred_web_search_tools=("mcp_tavily__tavily_search",),
            )
        ]
    )

    assert "mcp_tavily__tavily_search *web-search*" in rendered
    assert "secret" not in rendered.lower()


class _FakeMcpServer:
    def __init__(self, name: str, *, fail_connect: bool = False) -> None:
        self.name = name
        self.fail_connect = fail_connect
        self.cleaned = False

    async def connect(self) -> None:
        if self.fail_connect:
            raise RuntimeError("connect failed")

    async def cleanup(self) -> None:
        self.cleaned = True

    async def list_tools(self):
        return [SimpleNamespace(name="tavily_search", description="Search the web")]


class _GatedFakeMcpServer(_FakeMcpServer):
    def __init__(self, name: str, gate: asyncio.Event) -> None:
        super().__init__(name)
        self._gate = gate
        self.entered = asyncio.Event()

    async def connect(self) -> None:
        self.entered.set()
        await self._gate.wait()

