from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from deepy.audit import AuditPolicy
from deepy.config import Settings
from deepy.mcp import sdk_mcp_tool_name
from deepy.prompts import build_system_prompt
from deepy.skills import SkillInfo
from deepy.subagents import SubagentDefinition, discover_subagents
from deepy.tools import ToolRuntime
from deepy.tools.agents import build_function_tools
from deepy.tools.result import ToolResult

from .provider import ProviderBundle, build_provider_bundle

if TYPE_CHECKING:
    from agents.mcp import MCPServer


def build_deepy_agent(
    settings: Settings,
    runtime: ToolRuntime,
    *,
    project_root: Path,
    provider: ProviderBundle | None = None,
    loaded_skills: list[SkillInfo] | None = None,
    mcp_servers: list[MCPServer] | None = None,
    preferred_mcp_web_search_tools: list[str] | None = None,
    emit_event: Any | None = None,
    audit_policy: AuditPolicy | None = None,
):
    from agents import Agent

    provider = provider or build_provider_bundle(settings)
    main_tools = build_function_tools(
        runtime,
        mimo_schema_compatibility=uses_mimo_tool_schema_compatibility(
            settings.model.provider,
            settings.model.name,
        ),
        preferred_mcp_web_search_tools=preferred_mcp_web_search_tools,
        audit_policy=audit_policy,
    )
    subagent_tools = build_subagent_tools(
        settings,
        runtime,
        project_root=project_root,
        provider=provider,
        mcp_servers=list(mcp_servers or []),
        preferred_mcp_web_search_tools=preferred_mcp_web_search_tools or [],
        mimo_schema_compatibility=uses_mimo_tool_schema_compatibility(
            settings.model.provider,
            settings.model.name,
        ),
        emit_event=emit_event,
        audit_policy=audit_policy,
    )
    return Agent(
        name="Deepy",
        instructions=build_system_prompt(
            project_root,
            settings,
            loaded_skills=loaded_skills,
            preferred_mcp_web_search_tools=preferred_mcp_web_search_tools,
        ),
        model=provider.model,
        model_settings=provider.model_settings,
        tools=[*main_tools, *subagent_tools],
        mcp_servers=list(mcp_servers or []),
        mcp_config={"include_server_in_tool_names": True},
    )


def uses_mimo_tool_schema_compatibility(provider: str, model: str) -> bool:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip().lower()
    if normalized_provider == "xiaomi":
        return normalized_model in {"mimo-v2.5", "mimo-v2.5-pro"}
    if normalized_provider == "openrouter":
        return normalized_model in {"xiaomi/mimo-v2.5", "xiaomi/mimo-v2.5-pro"}
    return False


def build_subagent_tools(
    settings: Settings,
    runtime: ToolRuntime,
    *,
    project_root: Path,
    provider: ProviderBundle,
    mcp_servers: list[MCPServer],
    preferred_mcp_web_search_tools: list[str],
    mimo_schema_compatibility: bool = False,
    emit_event: Any | None = None,
    audit_policy: AuditPolicy | None = None,
) -> list[Any]:
    from agents import Agent

    discovery = discover_subagents(project_root)
    tools: list[Any] = []
    for definition in discovery.definitions:
        subagent = Agent(
            name=f"Deepy {definition.name}",
            instructions=_subagent_instructions(definition, preferred_mcp_web_search_tools),
            model=definition.model or provider.model,
            model_settings=provider.model_settings,
            tools=build_function_tools(
                runtime,
                mimo_schema_compatibility=mimo_schema_compatibility,
                preferred_mcp_web_search_tools=preferred_mcp_web_search_tools,
                include_tools=set(definition.tools),
                audit_policy=audit_policy,
            ),
            mcp_servers=_search_mcp_servers_for_subagent(
                definition,
                mcp_servers,
                preferred_mcp_web_search_tools,
            ),
            mcp_config={"include_server_in_tool_names": True},
        )
        tools.append(
            subagent.as_tool(
                tool_name=definition.tool_name,
                tool_description=definition.description,
                custom_output_extractor=_subagent_output_extractor(definition),
                on_stream=_subagent_stream_handler(definition, emit_event),
                max_turns=definition.max_turns,
            )
        )
    return tools


def _subagent_instructions(
    definition: SubagentDefinition,
    preferred_mcp_web_search_tools: list[str],
) -> str:
    search_mcp = ""
    if definition.mcp.inherit_search and preferred_mcp_web_search_tools:
        search_mcp = (
            "\n\nSearch-class MCP tools available to this subagent: "
            + ", ".join(preferred_mcp_web_search_tools)
            + ". Use them only for search/current-information work."
        )
    return (
        f"{definition.instructions.strip()}\n\n"
        "Return one concise final report to the main Deepy agent. Include assigned scope, "
        "key findings or actions, relevant file paths or commands, and unresolved issues. "
        "Do not ask the user directly; report blockers or approval needs to the main agent."
        f"{search_mcp}"
    )


def _subagent_output_extractor(definition: SubagentDefinition):
    async def extract(result: Any) -> str:
        output = getattr(result, "final_output", "")
        text = output if isinstance(output, str) else str(output or "")
        return ToolResult.ok_result(
            definition.tool_name,
            text,
            metadata={
                "kind": "subagent_result",
                "subagent": definition.name,
                "source": definition.source,
            },
        ).to_json()

    return extract


def _subagent_stream_handler(definition: SubagentDefinition, emit_event: Any | None):
    async def handle(event: Any) -> None:
        if emit_event is None:
            return
        from .events import DeepyStreamEvent, normalize_stream_event
        from deepy.ui.shared.render.message_view import format_tool_display_label

        normalized = normalize_stream_event(event)
        if normalized is None or normalized.kind != "tool_call":
            return
        nested_tool = normalized.name or "tool"
        emit_event(
            DeepyStreamEvent(
                kind="status",
                name=definition.tool_name,
                text=(
                    f"{format_tool_display_label(definition.tool_name)} progress - "
                    f"using {nested_tool}"
                ),
                payload={
                    "kind": "subagent_progress",
                    "subagent": definition.name,
                    "tool": nested_tool,
                },
            )
        )

    return handle


def _search_mcp_servers_for_subagent(
    definition: SubagentDefinition,
    servers: list[MCPServer],
    preferred_tools: list[str],
) -> list[MCPServer]:
    if not definition.mcp.inherit_search or not preferred_tools:
        return []
    allowed = set(preferred_tools)
    filtered: list[MCPServer] = []
    for server in servers:
        if not _looks_like_mcp_server(server):
            continue
        filtered.append(_SearchOnlyMcpServer(server, allowed))  # type: ignore[arg-type]
    return filtered


def _looks_like_mcp_server(server: object) -> bool:
    return all(hasattr(server, attr) for attr in ("call_tool", "list_tools", "name"))


def _mcp_server_base() -> type[Any]:
    from agents.mcp import MCPServer

    return MCPServer


class _SearchOnlyMcpServer(_mcp_server_base()):
    def __init__(self, wrapped: MCPServer, allowed_model_names: set[str]) -> None:
        super().__init__(
            use_structured_content=bool(getattr(wrapped, "use_structured_content", False)),
            failure_error_function=getattr(wrapped, "_failure_error_function", None),
        )
        self._wrapped = wrapped
        self._allowed_model_names = allowed_model_names

    @property
    def name(self) -> str:
        return str(getattr(self._wrapped, "name", "mcp"))

    @property
    def cached_tools(self) -> Any:
        return getattr(self._wrapped, "cached_tools", None)

    async def connect(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    async def list_tools(self, *args: Any, **kwargs: Any) -> list[Any]:
        listed = await self._wrapped.list_tools(*args, **kwargs)
        return [
            tool
            for tool in listed
            if sdk_mcp_tool_name(self.name, str(getattr(tool, "name", "")))
            in self._allowed_model_names
        ]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        meta: dict[str, Any] | None = None,
    ) -> Any:
        if sdk_mcp_tool_name(self.name, tool_name) not in self._allowed_model_names:
            raise PermissionError(f"MCP tool is not available to this subagent: {tool_name}")
        return await self._wrapped.call_tool(tool_name, arguments, meta)

    async def list_prompts(self) -> Any:
        return await self._wrapped.list_prompts()

    async def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self._wrapped.get_prompt(name, arguments)
