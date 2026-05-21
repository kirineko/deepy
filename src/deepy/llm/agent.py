from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from deepy.config import Settings
from deepy.prompts import build_system_prompt
from deepy.skills import SkillInfo
from deepy.tools import ToolRuntime
from deepy.tools.agents import build_function_tools

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
):
    from agents import Agent

    provider = provider or build_provider_bundle(settings)
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
        tools=build_function_tools(
            runtime,
            mimo_schema_compatibility=uses_mimo_tool_schema_compatibility(
                settings.model.provider,
                settings.model.name,
            ),
            preferred_mcp_web_search_tools=preferred_mcp_web_search_tools,
        ),
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
