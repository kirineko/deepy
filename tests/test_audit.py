from __future__ import annotations

import sys

import pytest
from rich.console import Console

from deepy.audit import (
    ApprovalDecision,
    AuditMode,
    AuditModeState,
    AuditPolicy,
    McpSafeTool,
    PendingApproval,
    parse_audit_mode,
)
from deepy.config import Settings, TestShellToolConfig as ShellTestToolConfig, ToolsConfig, load_settings
from deepy.llm.runner import run_prompt_once
from deepy.llm.provider import ProviderBundle
from deepy.tools import ToolRuntime
from deepy.tools.agents import build_function_tools
from deepy.ui.audit_approval_panel import build_approval_view, render_approval_panel
from deepy.utils import json as json_utils


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


def test_test_shell_approval_view_uses_test_command_title():
    view = build_approval_view(
        PendingApproval(
            index=0,
            name="test_shell",
            tool_name="test_shell",
            arguments=json_utils.dumps({"command": "cargo run"}),
            action_kind="command",
        )
    )

    assert view.title == "Approve test command?"
    assert view.target == "cargo run"


def test_update_approval_panel_omits_argument_summary_for_concise_audit_prompt(tmp_path):
    view = build_approval_view(
        PendingApproval(
            index=0,
            name="Update",
            tool_name="Update",
            arguments=json_utils.dumps(
                {
                    "path": "leetcode/two_sum.py",
                    "old": "print(s.twoSum([-1, -2, -3, -4, -5], -8))",
                    "new": "",
                }
            ),
            action_kind="text_write",
        ),
        project_root=tmp_path,
    )
    console = Console(record=True, width=100, color_system=None)

    console.print(render_approval_panel(view))
    rendered = console.export_text()

    assert view.target == "leetcode/two_sum.py"
    assert view.metadata == (("edits", "1"),)
    assert "path: leetcode/two_sum.py" in rendered
    assert "edits: 1" in rendered
    assert "summary:" not in rendered
    assert "old:" not in rendered
    assert "print(s.twoSum" not in rendered


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
async def test_test_shell_approval_policy_by_mode(tmp_path):
    runtime = ToolRuntime(cwd=tmp_path, settings=Settings())

    normal_tool = next(
        tool
        for tool in build_function_tools(
            runtime,
            include_tools={"test_shell"},
            audit_policy=AuditPolicy.from_mode(AuditMode.NORMAL),
        )
        if tool.name == "test_shell"
    )
    auto_tool = next(
        tool
        for tool in build_function_tools(
            runtime,
            include_tools={"test_shell"},
            audit_policy=AuditPolicy.from_mode(AuditMode.AUTO),
        )
        if tool.name == "test_shell"
    )
    yolo_tool = next(
        tool
        for tool in build_function_tools(
            runtime,
            include_tools={"test_shell"},
            audit_policy=AuditPolicy.from_mode(AuditMode.YOLO),
        )
        if tool.name == "test_shell"
    )

    assert await normal_tool.needs_approval(None, {"command": "cargo run"}, "call") is True
    assert await auto_tool.needs_approval(None, {"command": "cargo run"}, "call") is True
    assert await yolo_tool.needs_approval(None, {"command": "cargo run"}, "call") is False
    assert await normal_tool.needs_approval(None, {"command": "cargo test"}, "call") is False
    assert await normal_tool.needs_approval(None, {"command": "git push"}, "call") is False


@pytest.mark.asyncio
async def test_test_shell_audit_approved_invocation_uses_constrained_runner(tmp_path):
    command = f"{sys.executable} -c 'print(\"audit-ok\")'"
    settings = Settings(
        tools=ToolsConfig(
            test_shell=ShellTestToolConfig(approval_required_patterns=(f"{sys.executable} -c *",))
        )
    )
    runtime = ToolRuntime(cwd=tmp_path, settings=settings)
    tool = next(
        tool
        for tool in build_function_tools(
            runtime,
            include_tools={"test_shell"},
            audit_policy=AuditPolicy.from_mode(AuditMode.NORMAL),
        )
        if tool.name == "test_shell"
    )

    result = json_utils.loads(
        await tool.on_invoke_tool(None, json_utils.dumps({"command": command}))
    )

    assert result["ok"] is True
    assert result["name"] == "test_shell"
    assert result["metadata"]["approvedByAudit"] is True
    assert result["metadata"]["decision"] == "approval_required"
    assert "audit-ok" in result["metadata"]["stdout"]


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


@pytest.mark.asyncio
async def test_run_prompt_once_adds_file_mutation_preflight_to_pending_approval(monkeypatch, tmp_path):
    from agents import ModelSettings

    captured: list[PendingApproval] = []

    class FakeInterruption:
        name = "Write"
        arguments = '{"path":"app.py","content":"print(1)\\n"}'
        raw_item = {"name": "Write", "arguments": arguments}
        agent = type("Agent", (), {"name": "Deepy"})()

    class FakeState:
        def approve(self, interruption, *, always_approve=False):
            return None

        def reject(self, interruption, *, always_reject=False, rejection_message=None):
            return None

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

    def approval_resolver(pending: list[PendingApproval]) -> list[ApprovalDecision]:
        captured.extend(pending)
        assert not (tmp_path / "app.py").exists()
        return [ApprovalDecision("approve")]

    monkeypatch.setattr("agents.Runner", FakeRunner)

    await run_prompt_once(
        "write app",
        project_root=tmp_path,
        settings=Settings(),
        provider=ProviderBundle(client=object(), model="fake-model", model_settings=ModelSettings()),
        approval_resolver=approval_resolver,
    )

    assert captured
    assert captured[0].preflight is not None
    assert captured[0].preflight["ok"] is True
    assert "print(1)" in str(captured[0].preflight["metadata"]["diff"])
    assert not (tmp_path / "app.py").exists()
