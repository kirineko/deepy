"""Child Read capabilities must not depend on concurrent parent/child calls."""

import asyncio
import json

import pytest
from agents import Agent, ModelSettings
from openai import AsyncOpenAI

from deepy.config import Settings
from deepy.llm.agent import build_deepy_agent
from deepy.llm.provider import DeepyResponsesModel, ProviderBundle
from deepy.subagents import SubagentDefinition, SubagentDiscoveryResult
from deepy.tools import ToolRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize("parent_model", ["mimo-v2.5", "mimo-v2.5-pro"])
@pytest.mark.parametrize("batch", [False, True])
async def test_subagent_read_uses_effective_model(tmp_path, monkeypatch, parent_model, batch):
    (tmp_path / "image.png").write_bytes(b"image")
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    settings = Settings.from_mapping(
        {"active_provider": "mimo", "providers": {"mimo": {"model": parent_model}}}
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    definitions = tuple(
        SubagentDefinition(
            name=name, description="test", instructions="test", tools=("Read",), model=model
        )
        for name, model in (("inherit", None), ("vision", "mimo-v2.5"), ("text", "mimo-v2.5-pro"))
    )
    monkeypatch.setattr(
        "deepy.llm.agent.discover_subagents", lambda root: SubagentDiscoveryResult(definitions)
    )
    children = []
    original = Agent.as_tool

    def capture(self, **kwargs):
        children.append(self)
        return original(self, **kwargs)

    monkeypatch.setattr(Agent, "as_tool", capture)
    async with AsyncOpenAI(api_key="test") as client:
        parent = build_deepy_agent(
            settings,
            runtime,
            project_root=tmp_path,
            provider=ProviderBundle(
                client=client,
                model=DeepyResponsesModel(
                    provider="mimo", model=parent_model, openai_client=client
                ),
                model_settings=ModelSettings(),
            ),
        )
        request = (
            {"files": [{"path": "image.png"}, {"path": "notes.txt"}]}
            if batch
            else {"path": "image.png"}
        )
        agents = [parent, *children]
        outputs = await asyncio.gather(
            *(
                next(tool for tool in agent.tools if tool.name == "Read").on_invoke_tool(
                    None, json.dumps(request)
                )
                for agent in agents
            )
        )
    for output, supports_images in zip(
        outputs,
        [parent_model == "mimo-v2.5", parent_model == "mimo-v2.5", True, False],
        strict=True,
    ):
        result = json.loads(output)
        assert bool(result.get("followUpMessages")) == supports_images
        if not supports_images:
            if batch:
                assert result["metadata"]["failureCount"] == 1
                assert "不支持图片" in result["metadata"]["targets"][0]["error"]
            else:
                assert not result["ok"] and "不支持图片" in result["error"]
    assert runtime.settings is settings
    if batch:
        assert json.loads(runtime.write_v3("notes.txt", "updated", overwrite=True))["ok"]
