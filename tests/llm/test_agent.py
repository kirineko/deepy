from __future__ import annotations

from agents import ModelSettings

from deepy.config import ModelConfig, Settings
from deepy.llm.agent import build_deepy_agent, uses_mimo_tool_schema_compatibility
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
    assert {"subagent_explore", "subagent_reviewer", "subagent_tester"}.issubset(
        {tool.name for tool in agent.tools}
    )


def test_mimo_tool_schema_compatibility_detection():
    assert uses_mimo_tool_schema_compatibility("mimo", "mimo-v2.5")
    assert uses_mimo_tool_schema_compatibility("mimo", "mimo-v2.5-pro")
    assert not uses_mimo_tool_schema_compatibility("openrouter", "xiaomi/mimo-v2.5")
    assert not uses_mimo_tool_schema_compatibility("openrouter", "xiaomi/mimo-v2.5-pro")
    assert not uses_mimo_tool_schema_compatibility("openrouter", "google/gemini-3.5-flash")
    assert not uses_mimo_tool_schema_compatibility("deepseek", "deepseek-flash")


def test_build_deepy_agent_uses_mimo_compatible_tool_schema_for_xiaomi(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    settings = Settings(
        model=ModelConfig(
            provider="mimo",
            name="mimo-v2.5",
            base_url="https://api.xiaomimimo.com/v1",
            api_key="sk-test",
        )
    )

    agent = build_deepy_agent(
        settings,
        runtime,
        project_root=tmp_path,
        provider=ProviderBundle(
            client=object(),
            model="test-model",
            model_settings=ModelSettings(),
        ),
    )

    read_tool = next(tool for tool in agent.tools if tool.name == "Read")
    assert read_tool.params_json_schema["required"] == []
    assert read_tool.params_json_schema["properties"]["offset"]["type"] == "integer"
    assert read_tool.strict_json_schema is False


def test_build_deepy_agent_preserves_tool_schema_for_non_mimo_models(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())
    settings = Settings(
        model=ModelConfig(
            provider="kimi",
            name="kimi-k3",
            base_url="https://api.moonshot.cn/v1",
            api_key="sk-test",
        )
    )

    agent = build_deepy_agent(
        settings,
        runtime,
        project_root=tmp_path,
        provider=ProviderBundle(
            client=object(),
            model="test-model",
            model_settings=ModelSettings(),
        ),
    )

    read_tool = next(tool for tool in agent.tools if tool.name == "Read")
    assert read_tool.params_json_schema["required"] == []


def test_build_deepy_agent_exposes_subagents_without_raw_shell_in_tester(tmp_path):
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
    )

    subagent_names = {tool.name for tool in agent.tools if tool.name.startswith("subagent_")}

    assert subagent_names == {"subagent_explore", "subagent_reviewer", "subagent_tester"}
    assert "test_shell" not in {tool.name for tool in agent.tools}


def test_subagent_override_stays_in_active_provider(tmp_path, monkeypatch):
    from agents import Agent
    from openai import AsyncOpenAI
    from deepy.llm.provider import DeepyResponsesModel
    from deepy.subagents import SubagentDefinition, SubagentDiscoveryResult

    definitions = tuple(SubagentDefinition(name=name, description="test", instructions="test", tools=("Read",), model=model)
                        for name, model in [("inherit", None), ("valid", "mimo-v2.5-pro"), ("foreign", "kimi-k3"), ("unknown", "missing")])
    monkeypatch.setattr("deepy.llm.agent.discover_subagents", lambda root: SubagentDiscoveryResult(definitions))
    children = []
    original = Agent.as_tool

    def capture(self, **kwargs):
        children.append(self)
        return original(self, **kwargs)

    monkeypatch.setattr(Agent, "as_tool", capture)
    settings = Settings.from_mapping({"active_provider": "mimo"})
    client = AsyncOpenAI(api_key="test")
    model = DeepyResponsesModel(provider="mimo", model="mimo-v2.5", openai_client=client)
    events = []
    build_deepy_agent(settings, ToolRuntime(cwd=tmp_path, settings=settings), project_root=tmp_path,
                      provider=ProviderBundle(client=client, model=model, model_settings=ModelSettings()), emit_event=events.append)
    assert len(children) == 2
    assert children[0].model is model
    assert children[1].model.model == "mimo-v2.5-pro"
    assert children[1].model.provider == "mimo"
    assert len(events) == 2 and all("skipped" in event.text for event in events)
