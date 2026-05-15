from __future__ import annotations

from agents import ModelSettings

from deepy.config import Settings
from deepy.llm.agent import build_deepy_agent
from deepy.llm.provider import ProviderBundle
from deepy.tools import ToolRuntime


def test_build_deepy_agent_passes_mcp_servers_and_search_guidance(tmp_path):
    mcp_server = object()
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    agent = build_deepy_agent(
        Settings(),
        runtime,
        project_root=tmp_path,
        provider=ProviderBundle(
            client=object(),
            model="test-model",
            model_settings=ModelSettings(),
        ),
        mcp_servers=[mcp_server],
        preferred_mcp_web_search_tools=["mcp_tavily__tavily_search"],
    )

    assert agent.mcp_servers == [mcp_server]
    assert agent.mcp_config["include_server_in_tool_names"] is True
    assert "mcp_tavily__tavily_search" in agent.instructions
    assert any(tool.name == "WebSearch" for tool in agent.tools)
