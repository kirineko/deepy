from __future__ import annotations

import pytest

from deepy.audit import (
    ApprovalDecision,
    AuditMode,
    AuditModeState,
    AuditPolicy,
    McpSafeTool,
    parse_audit_mode,
)
from deepy.config import Settings, load_settings
from deepy.llm.runner import run_prompt_once
from deepy.llm.provider import ProviderBundle
from deepy.tools import ToolRuntime
from deepy.tools.agents import build_function_tools


def test_audit_mode_parsing_and_cycle():
    state = AuditModeState.from_value("normal")

    assert parse_audit_mode("AUTO") == AuditMode.AUTO
    assert parse_audit_mode("bad") == AuditMode.YOLO
    assert state.cycle() == AuditMode.AUTO
    assert state.cycle() == AuditMode.YOLO
    assert state.cycle() == AuditMode.NORMAL


def test_settings_load_audit_mode_and_mcp_safe_tools(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[audit]
mode = "auto"
mcp_safe_tools = [
  {server = "github", tool = "search_issues"},
]
""",
        encoding="utf-8",
    )

    settings = load_settings(config, env={})

    assert settings.audit.mode == AuditMode.AUTO
    assert settings.audit.mcp_safe_tools == (McpSafeTool("github", "search_issues"),)


@pytest.mark.asyncio
async def test_builtin_tool_approval_policy_by_mode(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    normal_tools = {
        tool.name: tool
        for tool in build_function_tools(runtime, audit_policy=AuditPolicy.from_mode(AuditMode.NORMAL))
    }
    auto_tools = {
        tool.name: tool
        for tool in build_function_tools(runtime, audit_policy=AuditPolicy.from_mode(AuditMode.AUTO))
    }
    yolo_tools = {
        tool.name: tool
        for tool in build_function_tools(runtime, audit_policy=AuditPolicy.from_mode(AuditMode.YOLO))
    }

    assert await normal_tools["Write"].needs_approval(None, {}, "call") is True
    assert await normal_tools["Update"].needs_approval(None, {}, "call") is True
    assert await normal_tools["shell"].needs_approval(None, {}, "call") is True
    assert await normal_tools["task_stop"].needs_approval(None, {}, "call") is True
    assert auto_tools["Read"].needs_approval is False
    assert await auto_tools["Write"].needs_approval(None, {}, "call") is False
    assert await auto_tools["shell"].needs_approval(None, {}, "call") is True
    assert await yolo_tools["shell"].needs_approval(None, {}, "call") is False


@pytest.mark.asyncio
async def test_run_prompt_once_approves_sdk_interruption(monkeypatch, tmp_path):
    from agents import ModelSettings

    class FakeInterruption:
        name = "shell"
        arguments = '{"command":"pwd"}'
        raw_item = {"name": "shell", "arguments": '{"command":"pwd"}'}
        agent = type("Agent", (), {"name": "Deepy"})()

    class FakeState:
        def __init__(self):
            self.approved = []
            self.rejected = []

        def approve(self, interruption, *, always_approve=False):
            self.approved.append((interruption.name, always_approve))

        def reject(self, interruption, *, always_reject=False, rejection_message=None):
            self.rejected.append((interruption.name, always_reject, rejection_message))

    state = FakeState()

    class InterruptedStream:
        final_output = None
        is_complete = False
        interruptions = [FakeInterruption()]

        async def stream_events(self):
            if False:
                yield None

        def to_state(self):
            return state

    class CompleteStream:
        final_output = "done"
        is_complete = True
        interruptions = []

        async def stream_events(self):
            if False:
                yield None

    calls = []

    class FakeRunner:
        @staticmethod
        def run_streamed(agent, input, max_turns, run_config, session):
            calls.append(input)
            return InterruptedStream() if len(calls) == 1 else CompleteStream()

    monkeypatch.setattr("agents.Runner", FakeRunner)

    summary = await run_prompt_once(
        "run pwd",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        approval_resolver=lambda pending: [ApprovalDecision("approve", always=True)],
    )

    assert summary.output == "done"
    assert state.approved == [("shell", True)]
    assert state.rejected == []
    assert calls[1] is state
