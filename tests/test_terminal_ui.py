from __future__ import annotations

import asyncio
import io
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from rich.cells import cell_len
from rich.console import Console

from deepy.background_tasks import BackgroundTaskManager
from deepy.config import ContextConfig, ModelConfig, Settings, UiConfig, load_settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.mcp import McpServerStatus
from deepy.sessions import DeepySession, SessionEntry, list_session_entries
from deepy.skill_market import MarketSkill
from deepy.status import BalanceInfo, BalanceStatus
from deepy.usage import TokenUsage
import deepy.ui.terminal as terminal
from deepy.ui import SlashCommand, parse_slash_command
from deepy.ui.local_command import LocalCommandResult
from deepy.ui.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.slash_commands import build_subagent_slash_prompt
from deepy.ui.skill_picker import SkillMenuAction
from deepy.ui.terminal import _collect_pending_question_response
from deepy.ui.terminal import _build_status_footer
from deepy.ui.terminal import _format_context_footer
from deepy.ui.terminal import _handle_slash_command
from deepy.ui.terminal import _print_assistant_output
from deepy.ui.terminal import _print_stream_event
from deepy.ui.terminal import _print_user_input
from deepy.ui.terminal import _print_usage_footer
from deepy.ui.terminal import _format_duration_ms
from deepy.ui.terminal import _format_stream_token_count_short
from deepy.ui.terminal import _format_token_count_short
from deepy.ui.terminal import _tool_output_text
from deepy.ui.terminal import _run_once_with_status
from deepy.ui.terminal import _working_status_text
from deepy.utils import json as json_utils


def _toolbar_text(toolbar: object) -> str:
    if callable(toolbar):
        toolbar = toolbar()
    return "".join(text for _style, text in toolbar) if isinstance(toolbar, list) else str(toolbar)


class _FakeStatusDisplay:
    def __enter__(self):
        return terminal._SilentStatus()

    def __exit__(self, *args):
        return None


def test_terminal_import_does_not_require_termios():
    code = """
import importlib.abc
import sys


class BlockTermios(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"termios", "tty"}:
            raise ImportError(fullname)
        return None


sys.meta_path.insert(0, BlockTermios())
import deepy.ui.terminal
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_history_tool_output_text_preserves_typed_content_for_parser():
    output = _tool_output_text(
        {
            "role": "function_call_output",
            "content": [{"type": "input_text", "text": "Detailed Results:\n\nTitle: x"}],
        }
    )

    assert output == '[{"type":"input_text","text":"Detailed Results:\\n\\nTitle: x"}]'


def test_windows_esc_watcher_sets_interrupt(monkeypatch):
    class FakeMsvcrt:
        @staticmethod
        def kbhit():
            return True

        @staticmethod
        def getwch():
            return "\x1b"

    interrupt_requested = terminal.threading.Event()
    stop_event = terminal.threading.Event()
    monkeypatch.setattr(terminal, "msvcrt", FakeMsvcrt)

    terminal._watch_windows_esc_keypress(interrupt_requested, stop_event)

    assert interrupt_requested.is_set()


def test_windows_esc_watcher_ignores_other_keys(monkeypatch):
    class FakeMsvcrt:
        calls = 0

        @classmethod
        def kbhit(cls):
            cls.calls += 1
            if cls.calls == 1:
                return True
            stop_event.set()
            return False

        @staticmethod
        def getwch():
            return "a"

    interrupt_requested = terminal.threading.Event()
    stop_event = terminal.threading.Event()
    monkeypatch.setattr(terminal, "msvcrt", FakeMsvcrt)

    terminal._watch_windows_esc_keypress(interrupt_requested, stop_event)

    assert not interrupt_requested.is_set()


def test_parse_slash_command_handles_argument():
    assert parse_slash_command("/resume abc123") == SlashCommand("resume", "abc123")


def test_parse_slash_command_ignores_regular_prompt():
    assert parse_slash_command("please edit this") is None


def test_parse_slash_command_strips_whitespace():
    assert parse_slash_command("  /exit  ") == SlashCommand("exit", "")


def test_skills_slash_command_shows_management_menu(tmp_path):
    console = Console(record=True)
    actions = iter([None])
    observed: list[tuple[object, object]] = []

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        terminal,
        "search_market_skills",
        lambda query: (_ for _ in ()).throw(AssertionError("market should load inside picker")),
    )
    monkeypatch.setattr(terminal, "_build_installed_skill_views", lambda project_root: ["installed-demo"])

    def fake_pick(market_skills, installed_skills, market_loader=None):
        observed.append((market_skills, installed_skills))
        assert market_loader is not None
        return next(actions)

    monkeypatch.setattr(terminal, "pick_skill_menu_action", fake_pick)
    try:
        next_session = _handle_slash_command(SlashCommand("skills"), console, tmp_path, "s1")
    finally:
        monkeypatch.undo()

    assert next_session == "s1"
    assert observed == [(None, ["installed-demo"])]


def test_skills_menu_install_action_asks_for_scope_and_runs_market_install(tmp_path, monkeypatch):
    console = Console(record=True)
    actions = iter([SkillMenuAction("choose-install-scope", "demo"), None])
    installed: list[tuple[str, str, Path]] = []

    monkeypatch.setattr(terminal, "search_market_skills", lambda query: ["market-demo"])
    monkeypatch.setattr(terminal, "list_installed_skills", lambda: [])
    monkeypatch.setattr(
        terminal,
        "pick_skill_menu_action",
        lambda market, installed, market_loader=None: next(actions),
    )
    monkeypatch.setattr(
        terminal,
        "pick_skill_install_scope",
        lambda name, home, project_root: SimpleNamespace(
            scope="project",
            path=project_root / ".agents" / "skills" / name,
        ),
    )

    def fake_install_market_skill(name, *, scope="user", project_root=None):
        assert project_root is not None
        install_path = project_root / ".agents" / "skills" / name
        installed.append((name, scope, install_path))
        return SimpleNamespace(name=name, scope=scope, install_path=install_path)

    monkeypatch.setattr(terminal, "install_market_skill", fake_install_market_skill)

    next_session = _handle_slash_command(SlashCommand("skills"), console, tmp_path, "s1")

    assert next_session == "s1"
    assert installed == [("demo", "project", tmp_path / ".agents" / "skills" / "demo")]
    assert "Installed skill: demo (project)" in console.export_text()


def test_skills_menu_includes_manual_user_and_project_skills(tmp_path, monkeypatch):
    home = tmp_path / "home"
    user_skill = home / ".agents" / "skills" / "user-demo"
    project_skill = tmp_path / ".agents" / "skills" / "project-demo"
    user_skill.mkdir(parents=True)
    project_skill.mkdir(parents=True)
    user_skill.joinpath("SKILL.md").write_text("---\nname: user-demo\n---\n", encoding="utf-8")
    project_skill.joinpath("SKILL.md").write_text("---\nname: project-demo\n---\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(terminal, "list_installed_skills", lambda: [])

    views = terminal._build_installed_skill_views(tmp_path)

    assert [(view.name, view.scope, view.path, view.managed_by_market) for view in views] == [
        ("project-demo", "project", project_skill, False),
        ("user-demo", "user", user_skill, False),
    ]


def test_skills_menu_remove_local_skill_deletes_standard_skill_dir(tmp_path):
    console = Console(record=True)
    skill_dir = tmp_path / ".agents" / "skills" / "manual"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text("---\nname: manual\n---\n", encoding="utf-8")
    loaded = ["manual"]

    changed = terminal._handle_skill_menu_action(
        SkillMenuAction("remove-local", "manual", scope="project", path=skill_dir),
        console,
        tmp_path,
        loaded,
        terminal.DARK_PALETTE,
    )

    assert changed is True
    assert not skill_dir.exists()
    assert loaded == []
    assert "Removed local skill: manual" in console.export_text()


def test_skills_menu_show_installed_skill_opens_detail_view(tmp_path, monkeypatch):
    console = Console(record=True)
    skill_dir = tmp_path / ".agents" / "skills" / "manual"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: manual\n---\n# Body\nUse this skill.",
        encoding="utf-8",
    )
    shown: list[object] = []

    monkeypatch.setattr(terminal, "show_skill_detail_view", shown.append)

    changed = terminal._handle_skill_menu_action(
        SkillMenuAction("show", "manual", scope="project", path=skill_dir),
        console,
        tmp_path,
        [],
        terminal.DARK_PALETTE,
    )

    assert changed is False
    assert len(shown) == 1
    detail = shown[0]
    assert detail.name == "manual"
    assert detail.scope == "project"
    assert detail.path == skill_dir
    assert "Use this skill." in detail.body
    assert detail.markdown is True
    assert "Use this skill." not in console.export_text()


def test_skills_menu_show_uninstalled_market_skill_opens_metadata_view(tmp_path, monkeypatch):
    console = Console(record=True)
    market_skill = MarketSkill(
        name="docx",
        description="Create Word documents.",
        version="1.0",
        uploaded_at="2026-05-15T00:00:00+00:00",
        sha256="abc123",
        installed=False,
    )
    shown: list[object] = []

    monkeypatch.setattr(terminal, "show_skill_detail_view", shown.append)
    monkeypatch.setattr(
        terminal,
        "find_skill",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("find_skill should not run for market metadata view")
        ),
    )

    changed = terminal._handle_skill_menu_action(
        SkillMenuAction("show", "docx", scope="market", market_skill=market_skill),
        console,
        tmp_path,
        [],
        terminal.DARK_PALETTE,
    )

    assert changed is False
    assert len(shown) == 1
    detail = shown[0]
    assert detail.name == "docx"
    assert detail.scope == "market"
    assert detail.description == "Create Word documents."
    assert detail.version == "1.0"
    assert detail.installed is False
    assert detail.markdown is True
    assert "Skill not installed" not in console.export_text()


def test_skills_list_command_lists_project_skills(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n",
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("skills", "list"), console, tmp_path, "s1")

    assert next_session == "s1"
    rendered = console.export_text()
    assert "Project skills:" in rendered
    assert "demo - Demo skill" in rendered


def test_skills_show_command_prints_skill_body(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Body\nUse this skill.",
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("skills", "show demo"), console, tmp_path, "s1")

    assert next_session == "s1"
    assert "Use this skill." in console.export_text()


def test_skills_use_command_loads_skill_name(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\nUse this skill.",
        encoding="utf-8",
    )
    console = Console(record=True)
    loaded: list[str] = []

    next_session = _handle_slash_command(SlashCommand("skills", "use demo"), console, tmp_path, "s1", loaded)

    assert next_session == "s1"
    assert loaded == ["demo"]
    assert "Loaded skill: demo" in console.export_text()


def test_new_slash_command_clears_loaded_skill_names(tmp_path):
    console = Console(record=True)
    loaded = ["demo"]

    next_session = _handle_slash_command(
        SlashCommand("new"),
        console,
        tmp_path,
        "s1",
        loaded,
    )

    assert next_session is None
    assert loaded == []


def test_resume_slash_command_selects_session_from_prompt(tmp_path, monkeypatch):
    console = Console(record=True)
    entries = [
        SessionEntry("s1", "s1.jsonl", active_tokens=10, created_at=1, updated_at=2),
        SessionEntry("s2", "s2.jsonl", active_tokens=20, created_at=3, updated_at=4),
    ]
    monkeypatch.setattr(terminal, "list_session_entries", lambda project_root: entries)

    next_session = _handle_slash_command(
        SlashCommand("resume"),
        console,
        tmp_path,
        "old",
        input_func=lambda prompt: "2",
    )

    rendered = console.export_text()
    assert next_session == "s2"
    assert "Resume a session (2 total)" in rendered
    assert "1. Untitled" in rendered
    assert "2. Untitled" in rendered
    assert "Resuming session s2" in rendered


def test_resume_slash_command_prints_selected_session_history(tmp_path):
    console = Console(record=True)
    session = DeepySession.create(tmp_path, session_id="s1")
    asyncio.run(
        session.add_items(
            [
                {"role": "user", "content": "当前项目是做什么的？"},
                {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": "先查看 README。"}],
                },
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "Read",
                    "arguments": '{"path":"README.md"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": '{"ok":true,"name":"Read","output":"","metadata":{"path":"README.md"}}',
                },
                {
                    "role": "assistant",
                    "content": "这是一个 **Python** 终端编程代理。",
                },
            ]
        )
    )

    next_session = _handle_slash_command(
        SlashCommand("resume"),
        console,
        tmp_path,
        "old",
        input_func=lambda prompt: "1",
        settings=Settings(ui=UiConfig(view_mode="full")),
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "当前项目是做什么的？" in rendered
    assert "Thinking" in rendered
    assert "[Read] README.md  ok" in rendered
    assert "这是一个 Python 终端编程代理。" in rendered


def test_resume_slash_command_keeps_current_session_on_invalid_selection(tmp_path, monkeypatch):
    console = Console(record=True)
    entries = [SessionEntry("s1", "s1.jsonl", active_tokens=10, created_at=1, updated_at=2)]
    monkeypatch.setattr(terminal, "list_session_entries", lambda project_root: entries)

    next_session = _handle_slash_command(
        SlashCommand("resume"),
        console,
        tmp_path,
        "old",
        input_func=lambda prompt: "missing",
    )

    assert next_session == "old"
    assert "Invalid session selection." in console.export_text()


def test_collect_pending_question_response_formats_selected_answers():
    console = Console(record=True)

    response = _collect_pending_question_response(
        console,
        [
            {
                "question": "Continue?",
                "options": [{"label": "Yes", "description": "Proceed."}, {"label": "No"}],
            }
        ],
        input_func=lambda prompt: "1",
    )

    assert response == (
        'User has answered your questions: "Continue?"="Yes". '
        "You can now continue with the user's answers in mind."
    )
    rendered = console.export_text()
    assert "Question: Continue?" in rendered
    assert "1. Yes - Proceed." in rendered


def test_collect_pending_question_response_declines_empty_answer():
    response = _collect_pending_question_response(
        Console(record=True),
        [{"question": "Continue?", "options": [{"label": "Yes"}]}],
        input_func=lambda prompt: "",
    )

    assert "declined to answer" in response


def test_collect_pending_question_response_accepts_multi_select_text():
    prompts: list[str] = []
    response = _collect_pending_question_response(
        Console(record=True),
        [
            {
                "question": "Which scopes?",
                "multiSelect": True,
                "options": [{"label": "tests"}, {"label": "docs"}],
            }
        ],
        input_func=lambda prompt: prompts.append(prompt) or "1, lint",
    )

    assert '"Which scopes?"="tests, lint"' in response
    assert prompts == ["Answer numbers separated by commas, custom text, or empty to decline"]


def test_collect_pending_question_response_prompts_for_custom_answer_option():
    prompts: list[str] = []
    answers = iter(["2", "Use pnpm"])
    response = _collect_pending_question_response(
        Console(record=True),
        [{"question": "Package manager?", "options": [{"label": "npm"}]}],
        input_func=lambda prompt: prompts.append(prompt) or next(answers),
    )

    assert '"Package manager?"="Use pnpm"' in response
    assert prompts == ["Answer number, custom text, or empty to decline", "Custom answer"]


def test_collect_pending_question_response_localizes_custom_answer_option():
    console = Console(record=True)
    prompts: list[str] = []
    answers = iter(["2", "使用 pnpm"])
    response = _collect_pending_question_response(
        console,
        [{"question": "选择哪个包管理器？", "options": [{"label": "npm"}]}],
        input_func=lambda prompt: prompts.append(prompt) or next(answers),
    )

    rendered = console.export_text()
    assert "自定义回答 - 输入自己的答案。" in rendered
    assert '"选择哪个包管理器？"="使用 pnpm"' in response
    assert prompts[-1] == "自定义回答"


def test_print_stream_event_merges_tool_call_and_output():
    console = Console(record=True)
    pending = {}

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="Read",
            payload={"call_id": "call-1", "arguments": '{"path":"/repo/README.md"}'},
        ),
        project_root="/repo",
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text='{"ok":true,"name":"Read","output":"","error":null,"metadata":{"path":"/tmp/a"}}',
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[Read] README.md  ok" in rendered
    assert "tool call:" not in rendered
    assert "tool output:" not in rendered


def test_print_stream_event_renders_subagent_lifecycle():
    console = Console(record=True)
    pending = {}
    task = """Please review the project.

## Scope
- HTML
- CSS
"""

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="subagent_explore",
            payload={"call_id": "sub-1", "arguments": json_utils.dumps({"input": task})},
        ),
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "sub-1"},
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "subagent_explore",
                    "output": "Found auth routing in src/app.py.",
                    "metadata": {"kind": "subagent_result", "subagent": "explore"},
                    "awaitUserResponse": False,
                }
            ),
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[Subagent] explore started" in rendered
    assert "Subagent Parameters" in rendered
    assert "Please review the project." in rendered
    assert "Scope" in rendered
    assert "[Subagent] explore  ok" in rendered
    assert "[Subagent] explore Please review" not in rendered


def test_print_stream_event_keeps_successful_subagent_report_with_rejection_text_ok():
    console = Console(record=True, width=120)
    pending = {}

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="subagent_explore",
            payload={
                "call_id": "sub-1",
                "arguments": json_utils.dumps({"input": "Check approval rendering"}),
            },
        ),
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "sub-1"},
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "subagent_explore",
                    "output": (
                        "The previous audit approval was rejected during investigation, "
                        "but the subagent completed successfully."
                    ),
                    "metadata": {"kind": "subagent_result", "subagent": "explore"},
                    "awaitUserResponse": False,
                }
            ),
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[Subagent] explore rejected" not in rendered
    assert "[Subagent] explore  ok" in rendered


def test_print_stream_event_renders_retryable_invalid_arguments_quietly():
    console = Console(record=True)
    pending = {}
    large_content = "SECRET_CONTENT" * 20

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="Write",
            payload={
                "call_id": "call-1",
                "arguments": (
                    '{"path":"/repo/app/page.tsx","content":'
                    f"{large_content},\"overwrite\":true,\"snapshot_id\":snapshot_4}}"
                ),
            },
        ),
        project_root="/repo",
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text=json_utils.dumps(
                {
                    "ok": False,
                    "name": "Write",
                    "output": "",
                    "error": "Invalid tool arguments JSON",
                    "metadata": {
                        "error_code": "invalid_arguments",
                        "retryable": True,
                        "recovery": "Pass valid JSON.",
                    },
                    "awaitUserResponse": False,
                }
            ),
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[Write] app/page.tsx (malformed args)  retryable - Pass valid JSON." in rendered
    assert "SECRET_CONTENT" not in rendered


def test_print_stream_event_hides_tool_call_until_output():
    console = Console(record=True)
    pending = {}

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="WebFetch",
            payload={
                "call_id": "call-1",
                "arguments": '{"url":"https://leetcode.cn/problems/two-sum/description/"}',
            },
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert rendered == ""
    assert pending["call-1"].summary == (
        "[WebFetch] https://leetcode.cn/problems/two-sum/description/"
    )


def test_print_stream_event_does_not_dump_unknown_tool_output_without_debug_env():
    console = Console(record=True)

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text='{"name":"mystery","value":{"nested":true}}',
        ),
        pending_tool_calls={},
    )

    rendered = console.export_text()
    assert "[Mystery]" in rendered
    assert "unknown" in rendered
    assert "Tool output JSON:" not in rendered
    assert '"nested": true' not in rendered


def test_print_stream_event_debug_env_dumps_successful_tool_output_json(monkeypatch):
    console = Console(record=True)
    monkeypatch.setenv("DEEPY_DEBUG_TOOL_OUTPUT", "1")

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text='[{"type":"input_text","text":"Detailed Results:\\n\\nTitle: x"}]',
        ),
        pending_tool_calls={},
    )

    rendered = console.export_text()
    assert "[MCP]" in rendered
    assert "ok" in rendered
    assert "Tool output JSON:" in rendered
    assert '"type": "input_text"' in rendered


def test_print_stream_event_renders_diff_without_headers_or_markers():
    console = Console(record=True, width=120)
    output = {
        "ok": True,
        "name": "Update",
        "output": "Edited file",
        "error": None,
        "metadata": {
            "path": "/repo/src/lib.rs",
            "diff": "--- a//repo/src/lib.rs\n+++ b//repo/src/lib.rs\n@@ -1,1 +1,1 @@\n-old\n+new\n same\n",
        },
        "awaitUserResponse": False,
    }

    _print_stream_event(
        console,
        DeepyStreamEvent(kind="tool_output", text=json_utils.dumps(output)),
        project_root="/repo",
    )

    rendered = console.export_text()
    assert "[Update]  ok" not in rendered
    assert "[Update] src/lib.rs (+1 -1)" in rendered
    assert "[Update] /repo/src/lib.rs (+1 -1)" not in rendered
    assert "old" in rendered
    assert "new" in rendered
    assert "same" in rendered
    assert "---" not in rendered
    assert "+++" not in rendered
    assert "@@" not in rendered
    assert "-old" not in rendered
    assert "+new" not in rendered


def test_print_stream_event_renders_write_preview_after_status():
    console = Console(record=True, width=120)
    output = {
        "ok": True,
        "name": "Write",
        "output": "Wrote file",
        "error": None,
        "metadata": {
            "path": "/repo/src/lib.rs",
            "diff": "--- /dev/null\n+++ b//repo/src/lib.rs\n@@ -0,0 +1,1 @@\n+new file body\n",
        },
        "awaitUserResponse": False,
    }

    _print_stream_event(
        console,
        DeepyStreamEvent(kind="tool_output", text=json_utils.dumps(output)),
    )

    rendered = console.export_text()
    assert "[Write]  ok" not in rendered
    assert "[Write] /repo/src/lib.rs (+1 -0)" in rendered
    assert "new file body" in rendered
    assert "+new file body" not in rendered
    assert "Edited" not in rendered


def test_print_stream_event_renders_audit_rejection_as_tool_status():
    console = Console(record=True, width=120)
    pending: dict[str, terminal.ToolCallDisplay] = {}

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="shell",
            payload={
                "call_id": "call-1",
                "arguments": json_utils.dumps(
                    {
                        "command": "rm -rf leetcode",
                        "description": "remove leetcode directory",
                    }
                ),
            },
        ),
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text="Tool execution was rejected by the user audit approval decision.",
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[Shell] rejected" in rendered
    assert " raw" not in rendered
    assert "rm -rf leetcode" not in rendered


def test_print_stream_event_passes_console_width_to_diff_preview(monkeypatch):
    console = Console(record=True, width=72)
    captured: dict[str, int | None] = {}
    output = {
        "ok": True,
        "name": "Update",
        "output": "Edited file",
        "error": None,
        "metadata": {
            "path": "/repo/src/lib.rs",
            "diff": "--- a//repo/src/lib.rs\n+++ b//repo/src/lib.rs\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        },
        "awaitUserResponse": False,
    }

    def fake_render_tool_diff_preview(text, *, palette=None, width=None, project_root=None):
        del text, palette, project_root
        captured["width"] = width
        return None

    monkeypatch.setattr(terminal, "render_tool_diff_preview", fake_render_tool_diff_preview)

    _print_stream_event(
        console,
        DeepyStreamEvent(kind="tool_output", text=json_utils.dumps(output)),
    )

    assert captured["width"] == 72


def test_print_stream_event_write_call_summary_hides_content_argument():
    console = Console(record=True, width=120)
    pending = {}

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="Write",
            payload={
                "call_id": "call-1",
                "arguments": json_utils.dumps(
                    {
                        "path": "/repo/src/lib.rs",
                        "content": "fn main() {\n    println!(\"hi\");\n}\n",
                    }
                ),
            },
        ),
        project_root="/repo",
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "Write",
                    "output": "Wrote file",
                    "error": None,
                    "metadata": {
                        "path": "/repo/src/lib.rs",
                        "diff": "--- /dev/null\n+++ b//repo/src/lib.rs\n@@ -0,0 +1,1 @@\n+fn main() {}\n",
                    },
                    "awaitUserResponse": False,
                }
            ),
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[Write] src/lib.rs (3 lines, 34 chars)  ok" not in rendered
    assert "println" not in rendered
    assert "fn main() {}" in rendered


def test_print_stream_event_ask_user_question_hides_question_arguments():
    console = Console(record=True, width=160)
    pending = {}

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_call",
            name="AskUserQuestion",
            payload={
                "call_id": "call-1",
                "arguments": json_utils.dumps(
                    {
                        "questions": [
                            {
                                "question": "Which path?",
                                "options": [{"label": "fast"}, {"label": "thorough"}],
                            }
                        ]
                    }
                ),
            },
        ),
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "AskUserQuestion",
                    "output": "Waiting for user input.",
                    "error": None,
                    "metadata": {"kind": "ask_user_question", "questions": []},
                    "awaitUserResponse": True,
                }
            ),
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[AskUserQuestion]  ok - Waiting for user input." in rendered
    assert "Which path?" not in rendered
    assert "questions" not in rendered


def test_print_stream_event_renders_shell_output_block():
    console = Console(record=True, width=120)

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            text=json_utils.dumps(
                {
                    "ok": False,
                    "name": "shell",
                    "output": "stdout line\nstderr line",
                    "error": "Command exited with code 1.",
                    "metadata": {"exitCode": 1},
                    "awaitUserResponse": False,
                }
            ),
        ),
    )

    rendered = console.export_text()
    assert "[Shell]  failed - Command exited with code 1." in rendered
    assert "stdout line" in rendered
    assert "stderr line" in rendered


def test_print_stream_event_renders_todo_board_separate_from_footer():
    console = Console(record=True, width=120)

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "todo_write",
                    "output": "Todo list updated",
                    "metadata": {
                        "kind": "todo_list",
                        "todos": [
                            {"id": "one", "content": "Inspect code", "status": "completed"},
                            {"id": "two", "content": "Implement board", "status": "in_progress"},
                        ],
                    },
                    "awaitUserResponse": False,
                }
            ),
        ),
    )

    rendered = console.export_text()
    assert "[Todo]  ok - 1/2 - Implement board" in rendered
    assert "Progress 1/2 · Current: Implement board" in rendered
    assert "  │ [x] Inspect code" in rendered
    assert "Todo List" not in rendered
    assert "model deepseek" not in rendered
    assert "ctx " not in rendered


def test_status_line_emphasizes_only_tool_label():
    line = terminal._status_line("[Read] Cargo.toml  ok", "green")

    assert line.plain == "• [Read] Cargo.toml  ok"
    label_style = str(line.spans[1].style)
    detail_style = str(line.spans[2].style)
    assert "bold" in label_style
    assert "underline" in label_style
    assert "bold" not in detail_style


def test_print_user_input_uses_prompt_marker():
    console = Console(record=True)

    _print_user_input(console, "hello\nworld")

    rendered = console.export_text()
    assert "> hello" in rendered
    assert "  world" in rendered


def test_submitted_prompt_echo_rows_accounts_for_multiline_and_wrapping():
    assert terminal._submitted_prompt_echo_rows("hello\nworld", 80) == 2
    assert terminal._submitted_prompt_echo_rows("你好\nworld", 80) == 2
    assert terminal._submitted_prompt_echo_rows("123456789", 5) == 4


def test_clear_submitted_prompt_echo_clears_each_rendered_row(monkeypatch):
    class TtyBuffer(io.StringIO):
        def isatty(self):
            return True

    stream = TtyBuffer()
    console = Console(file=stream, force_terminal=True, width=20)
    monkeypatch.setattr(terminal.shutil, "get_terminal_size", lambda fallback: os.terminal_size((20, 24)))

    terminal._clear_submitted_prompt_echo(console, "hello\nworld")

    assert stream.getvalue() == "\x1b[1A\x1b[2K\x1b[1A\x1b[2K\r"


def test_terminal_stream_renderer_flushes_reasoning_summary():
    console = Console(record=True)
    renderer = terminal.TerminalStreamRenderer(console, view_mode="full")

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="让我先看看项目结构。"))
    renderer.flush()

    rendered = console.export_text()
    assert "Thinking" in rendered
    assert "让我先看看项目结构。" in rendered


def test_terminal_stream_renderer_hides_reasoning_in_concise_view():
    class FakeStatus:
        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    console = Console(record=True)
    status = FakeStatus()
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=time.monotonic(),
        view_mode="concise",
    )

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="隐藏的思考。"))
    renderer.flush()

    rendered = console.export_text()
    assert "Thinking" not in rendered
    assert "隐藏的思考" not in rendered
    assert status.updates
    assert "↓" in status.updates[-1]


def test_terminal_stream_renderer_interleaves_reasoning_and_tool_calls():
    console = Console(record=True, width=160)
    renderer = terminal.TerminalStreamRenderer(console, project_root="/repo", view_mode="full")

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="先抓取题目。"))
    renderer(
        DeepyStreamEvent(
            kind="tool_call",
            name="WebFetch",
            payload={
                "call_id": "call-1",
                "arguments": '{"url":"https://leetcode.cn/problems/two-sum/description/"}',
            },
        )
    )
    renderer(
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "WebFetch",
                    "output": "Fetched page",
                    "error": None,
                    "metadata": {},
                    "awaitUserResponse": False,
                }
            ),
        )
    )
    renderer(DeepyStreamEvent(kind="reasoning_delta", text="再看项目结构。"))
    renderer(
        DeepyStreamEvent(
            kind="tool_call",
            name="shell",
            payload={"call_id": "call-2", "arguments": '{"command":"ls -la"}'},
        )
    )
    renderer(
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-2"},
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "shell",
                    "output": "README.md",
                    "error": None,
                    "metadata": {},
                    "awaitUserResponse": False,
                }
            ),
        )
    )
    renderer.flush()

    rendered = console.export_text()
    first_reasoning = rendered.index("先抓取题目。")
    webfetch = rendered.index("[WebFetch] https://leetcode.cn/problems/two-sum/description/")
    second_reasoning = rendered.index("再看项目结构。")
    shell = rendered.index("[Shell] ls -la")
    assert first_reasoning < webfetch < second_reasoning < shell


def test_terminal_stream_renderer_flushes_reasoning_for_each_model_turn():
    console = Console(record=True)
    renderer = terminal.TerminalStreamRenderer(console, view_mode="full")

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="第一轮思考。"))
    renderer.flush()
    renderer(DeepyStreamEvent(kind="reasoning_delta", text="第二轮思考。"))
    renderer.flush()

    rendered = console.export_text()
    assert "第一轮思考。" in rendered
    assert "第二轮思考。" in rendered


def test_terminal_stream_renderer_flushes_full_reasoning_without_truncation():
    console = Console(record=True, width=120)
    renderer = terminal.TerminalStreamRenderer(console, view_mode="full")
    content = "\n".join(f"步骤 {index}" for index in range(80))

    renderer(DeepyStreamEvent(kind="reasoning_delta", text=content))
    renderer.flush()

    rendered = console.export_text()
    assert "步骤 0" in rendered
    assert "步骤 79" in rendered
    assert "[truncated]" not in rendered


def test_terminal_stream_renderer_keeps_reasoning_visible_under_status_refresh():
    console = Console(record=True, width=120)
    started_at = time.monotonic()
    content = "用户用中文问候，我也应该用中文回复。这是第二段完整思考。"

    with console.status(_working_status_text(started_at), spinner="dots") as status:
        renderer = terminal.TerminalStreamRenderer(
            console,
            status=status,
            status_started_at=started_at,
            view_mode="full",
        )
        for char in content:
            renderer(DeepyStreamEvent(kind="reasoning_delta", text=char))
        renderer.flush()

    rendered = console.export_text()
    assert "[Thinking]" in rendered
    assert "用户用中文问候，我也应该用中文回复。" in rendered
    assert "这是第二段完整思考。" in rendered
    assert "用\n户" not in rendered
    assert "中\n文" not in rendered


def test_terminal_stream_renderer_restores_status_for_silent_text_generation(tmp_path):
    class FakeStatus:
        inline_output_flow = True
        active = False

        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.active = True
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    console = Console(record=True, width=120)
    status = FakeStatus()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=time.monotonic(),
        footer=footer,
        view_mode="full",
    )

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="准备输出最终答案。"))
    renderer(DeepyStreamEvent(kind="text_delta", text="最终答案片段"))

    rendered = console.export_text()
    assert "准备输出最终答案。" in rendered
    assert status.updates
    assert "↓" in status.updates[-1]
    assert "准备输出最终答案" not in status.updates[-1]


def test_terminal_stream_renderer_accumulates_stream_tokens_across_reasoning_and_output(
    tmp_path,
    monkeypatch,
):
    class FakeStatus:
        active = False

        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.active = True
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    monkeypatch.setattr(terminal, "estimate_tokens_for_text", len)
    console = Console(record=True, width=120)
    status = FakeStatus()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=time.monotonic(),
        footer=footer,
        view_mode="concise",
    )

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="abc"))
    renderer(DeepyStreamEvent(kind="text_delta", text="de"))

    assert status.updates
    assert "↓ 5 tokens" in status.updates[-1]
    assert "Responding" in status.updates[-1]
    assert "time " in status.updates[-1]
    assert status.updates[-1].index("↓ 5 tokens") < status.updates[-1].index("esc to interrupt")


def test_terminal_stream_renderer_counts_silent_tool_arguments_with_short_units(tmp_path, monkeypatch):
    class FakeStatus:
        inline_output_flow = True
        active = False

        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.active = True
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    monkeypatch.setattr(terminal, "estimate_tokens_for_text", len)
    console = Console(record=True, width=120)
    status = FakeStatus()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=time.monotonic(),
        footer=footer,
        view_mode="concise",
    )

    renderer(
        DeepyStreamEvent(
            kind="raw_response",
            name="response.function_call_arguments.delta",
            text="x" * 1100,
        )
    )

    rendered = console.export_text()
    assert rendered == ""
    assert status.updates
    assert "↓ 1.1K tokens" in status.updates[-1]


def test_terminal_stream_renderer_throttles_inline_stream_token_repaints(tmp_path, monkeypatch):
    class FakeStatus:
        inline_output_flow = True
        active = True

        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.active = True
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    monkeypatch.setattr(terminal, "estimate_tokens_for_text", len)
    console = Console(record=True, width=120)
    status = FakeStatus()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=time.monotonic(),
        footer=footer,
        view_mode="concise",
    )

    renderer(DeepyStreamEvent(kind="raw_response", text="abc"))
    renderer(DeepyStreamEvent(kind="raw_response", text="de"))

    assert len(status.updates) == 1
    assert "↓ 3 tokens" in status.updates[0]
    assert renderer.status_detail == "↓ 5 tokens"


def test_terminal_stream_renderer_refresh_restores_status_after_reasoning_pause(
    tmp_path,
    monkeypatch,
):
    class FakeStatus:
        inline_output_flow = True
        active = False

        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.active = True
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    now = 100.0
    monkeypatch.setattr(terminal.time, "monotonic", lambda: now)
    console = Console(record=True, width=120)
    status = FakeStatus()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=now,
        footer=footer,
        view_mode="full",
    )

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="这里之后模型会静默一段时间。"))
    now = 100.5
    renderer.refresh_status()
    assert status.updates == []

    now = 101.1
    renderer.refresh_status()

    rendered = console.export_text()
    assert "这里之后模型会静默一段时间。" in rendered
    assert status.updates
    assert "↓" in status.updates[-1]
    assert "这里之后模型会静默一段时间" not in status.updates[-1]


def test_terminal_stream_renderer_keeps_reasoning_text_out_of_status_footer(tmp_path):
    class FakeStatus:
        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    console = Console(record=True, width=120)
    status = FakeStatus()
    started_at = time.monotonic()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-pro", thinking=True, reasoning_effort="max"),
        ),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=started_at,
        footer=footer,
        view_mode="full",
    )

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="第一段很长的思考内容。"))
    renderer(DeepyStreamEvent(kind="reasoning_delta", text="第二段仍然是正文，不应该进入 footer。"))
    renderer.flush()

    rendered = console.export_text()
    assert "第一段很长的思考内容。" in rendered
    assert "第二段仍然是正文，不应该进入 footer。" in rendered
    assert status.updates
    assert "↓" in status.updates[-1]
    assert "第一段很长的思考内容" not in status.updates[-1]
    assert "第二段仍然是正文" not in status.updates[-1]


def test_terminal_stream_renderer_shows_tool_status_without_call_id(tmp_path):
    class FakeStatus:
        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    console = Console(record=True, width=120)
    status = FakeStatus()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=time.monotonic(),
        footer=footer,
        project_root=str(tmp_path),
    )

    renderer(
        DeepyStreamEvent(
            kind="tool_call",
            name="Write",
            payload={"arguments": json_utils.dumps({"path": str(tmp_path / "README.md")})},
        )
    )

    assert any("Write" in update and "README.md" not in update for update in status.updates)
    assert all("tool [Write]" not in update for update in status.updates)


def test_terminal_stream_renderer_shows_mcp_tool_status_without_arguments(tmp_path):
    class FakeStatus:
        def __init__(self) -> None:
            self.updates: list[str] = []

        def update(self, value) -> None:
            self.updates.append(value.plain if hasattr(value, "plain") else str(value))

    console = Console(record=True, width=120)
    status = FakeStatus()
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
    )
    renderer = terminal.TerminalStreamRenderer(
        console,
        status=status,
        status_started_at=time.monotonic(),
        footer=footer,
        project_root=str(tmp_path),
    )

    renderer(
        DeepyStreamEvent(
            kind="tool_call",
            name="mcp_tavily__tavily_extract",
            payload={"arguments": json_utils.dumps({"url": "https://example.com/very/long/path"})},
        )
    )

    assert status.updates
    assert "MCP" in status.updates[-1]
    assert "example.com" not in status.updates[-1]
    assert status.updates[-1].index("MCP") < status.updates[-1].index("esc to interrupt")


def test_terminal_stream_renderer_serializes_tool_output_with_output_lock():
    class RecordingLock:
        def __init__(self):
            self.entries = 0

        def __enter__(self):
            self.entries += 1
            return self

        def __exit__(self, *args):
            return None

    lock = RecordingLock()
    console = Console(record=True, width=120)
    renderer = terminal.TerminalStreamRenderer(console, output_lock=lock)

    renderer(
        DeepyStreamEvent(
            kind="tool_output",
            text=json_utils.dumps(
                {
                    "ok": True,
                    "name": "WebSearch",
                    "output": "Search results",
                    "error": None,
                    "metadata": {},
                    "awaitUserResponse": False,
                }
            ),
        )
    )

    assert lock.entries >= 1
    assert "[WebSearch]" in console.export_text()


def test_status_slash_command_prints_status(tmp_path, monkeypatch):
    console = Console(record=True, width=200)
    calls = 0

    def fake_fetch(settings):
        nonlocal calls
        calls += 1
        return BalanceStatus(is_available=True)

    monkeypatch.setattr(terminal, "fetch_deepseek_balance", fake_fetch)

    next_session = _handle_slash_command(SlashCommand("status"), console, tmp_path, "s1")

    assert next_session == "s1"
    rendered = console.export_text()
    assert calls == 1
    assert "Deepy Status" in rendered
    assert f"project        {tmp_path}" in rendered
    assert "balance" in rendered


def test_status_slash_command_does_not_fetch_balance_for_third_party_provider(tmp_path, monkeypatch):
    console = Console(record=True, width=200)

    def fail_fetch(settings):
        raise AssertionError("balance lookup should not run")

    monkeypatch.setattr(terminal, "fetch_deepseek_balance", fail_fetch)

    next_session = _handle_slash_command(
        SlashCommand("status"),
        console,
        tmp_path,
        "s1",
        settings=Settings(
            model=ModelConfig(
                provider="openrouter",
                name="xiaomi/mimo-v2.5-pro",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test",
            )
        ),
    )

    assert next_session == "s1"
    rendered = console.export_text()
    assert "balance" in rendered
    assert "unsupported provider" in rendered


def test_model_slash_command_lists_models(tmp_path):
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("model", "list"), console, tmp_path, "s1")

    rendered = console.export_text()
    assert next_session == "s1"
    assert "Available providers and models:" in rendered
    assert "openrouter" in rendered
    assert "xiaomi" in rendered
    assert "deepseek-v4-pro" in rendered
    assert "deepseek-v4-flash" in rendered
    assert "thinking:" in rendered
    assert "none" in rendered
    assert "high" in rendered
    assert "max" in rendered
    assert "enabled" in rendered


def test_model_slash_command_sets_model_and_reasoning_directly(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key = "sk-test"\nname = "deepseek-v4-pro"\nthinking = true\nreasoning_effort = "max"\n',
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("model", "set deepseek-v4-flash high"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(api_key="sk-test")),
    )

    rendered = console.export_text()
    text = config.read_text(encoding="utf-8")
    assert next_session == "s1"
    assert "Saved provider: deepseek · model: deepseek-v4-flash · thinking: high" in rendered
    assert 'api_key = "sk-test"' in text
    assert 'provider = "deepseek"' in text
    assert 'name = "deepseek-v4-flash"' in text
    assert 'thinking = true' in text
    assert 'reasoning_effort = "high"' in text


def test_model_slash_command_sets_reasoning_none_directly(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\nname = "deepseek-v4-pro"\nthinking = true\nreasoning_effort = "max"\n',
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("model", "reasoning none"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(name="deepseek-v4-pro")),
    )

    assert next_session == "s1"
    assert "Saved provider: deepseek · model: deepseek-v4-pro · thinking: none" in console.export_text()
    assert 'thinking = false' in config.read_text(encoding="utf-8")


def test_model_slash_command_sets_openrouter_provider_model_and_thinking(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key = "sk-test"\nname = "deepseek-v4-pro"\n',
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("model", "set openrouter xiaomi/mimo-v2.5-pro disabled"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(api_key="sk-test")),
    )

    text = config.read_text(encoding="utf-8")
    rendered = console.export_text()
    assert next_session == "s1"
    assert "Saved provider: openrouter · model: xiaomi/mimo-v2.5-pro · thinking: none" in rendered
    assert "Provider switched to openrouter" in rendered
    assert "Reconfigure the API key" in rendered
    assert "https://openrouter.ai/workspaces/default/keys" in rendered
    assert 'api_key = "sk-test"' in text
    assert 'provider = "openrouter"' in text
    assert 'name = "xiaomi/mimo-v2.5-pro"' in text
    assert 'base_url = "https://openrouter.ai/api/v1"' in text
    assert 'thinking = false' in text
    assert 'reasoning_effort = "none"' in text


def test_model_slash_command_sets_xiaomi_enabled_without_high_effort(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key = "sk-test"\nname = "deepseek-v4-pro"\n',
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("model", "set xiaomi mimo-v2.5 enabled"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(api_key="sk-test")),
    )

    text = config.read_text(encoding="utf-8")
    assert next_session == "s1"
    assert "Saved provider: xiaomi · model: mimo-v2.5 · thinking: enabled" in console.export_text()
    assert 'provider = "xiaomi"' in text
    assert 'name = "mimo-v2.5"' in text
    assert 'thinking = true' in text
    assert 'reasoning_effort = "enabled"' in text
    assert 'reasoning_effort = "high"' not in text


def test_model_slash_command_rejects_invalid_values_without_changing_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\nname = "deepseek-v4-pro"\n', encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("model", "set deepseek-chat medium"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(name="deepseek-v4-pro")),
    )

    assert next_session == "s1"
    assert "Invalid model:" in console.export_text()
    assert config.read_text(encoding="utf-8") == '[model]\nname = "deepseek-v4-pro"\n'


def test_model_slash_command_uses_numbered_selection(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\nname = "deepseek-v4-pro"\n', encoding="utf-8")
    console = Console(record=True)
    answers = iter(["2", "1", "3"])

    next_session = _handle_slash_command(
        SlashCommand("model"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(api_key="sk-test")),
        input_func=lambda prompt: next(answers),
    )

    rendered = console.export_text()
    text = config.read_text(encoding="utf-8")
    assert next_session == "s1"
    assert "Current provider: deepseek · model: deepseek-v4-pro · thinking: max" in rendered
    assert "Providers:" in rendered
    assert "Models for openrouter:" in rendered
    assert "Thinking:" in rendered
    assert "Saved provider: openrouter · model: xiaomi/mimo-v2.5-pro · thinking: xhigh" in rendered
    assert "Provider switched to openrouter" in rendered
    assert "https://openrouter.ai/workspaces/default/keys" in rendered
    assert 'provider = "openrouter"' in text
    assert 'name = "xiaomi/mimo-v2.5-pro"' in text
    assert 'thinking = true' in text
    assert 'reasoning_effort = "xhigh"' in text


def test_model_slash_command_cancels_without_saving(tmp_path):
    config = tmp_path / "config.toml"
    original = '[model]\nname = "deepseek-v4-pro"\n'
    config.write_text(original, encoding="utf-8")
    console = Console(record=True)
    answers = iter(["2", ""])

    next_session = _handle_slash_command(
        SlashCommand("model"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(name="deepseek-v4-pro")),
        input_func=lambda prompt: next(answers),
    )

    assert next_session == "s1"
    assert "Model unchanged." in console.export_text()
    assert config.read_text(encoding="utf-8") == original


def test_model_slash_command_uses_keyboard_pickers_when_no_input_func(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\nname = "deepseek-v4-pro"\n', encoding="utf-8")
    console = Console(record=True)
    monkeypatch.setattr(terminal, "pick_provider", lambda current: "deepseek")
    monkeypatch.setattr(terminal, "pick_model", lambda current, *, provider: "deepseek-v4-flash")
    monkeypatch.setattr(terminal, "pick_reasoning_mode", lambda current, *, provider: "high")

    next_session = _handle_slash_command(
        SlashCommand("model"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(name="deepseek-v4-pro")),
    )

    text = config.read_text(encoding="utf-8")
    assert next_session == "s1"
    assert "Saved provider: deepseek · model: deepseek-v4-flash · thinking: high" in console.export_text()
    assert 'name = "deepseek-v4-flash"' in text
    assert 'reasoning_effort = "high"' in text


def test_help_slash_command_includes_model(tmp_path):
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("help"), console, tmp_path, "s1")

    rendered = console.export_text()
    assert next_session == "s1"
    assert "/model" in rendered
    assert "/init" in rendered
    assert "/mcp" in rendered
    assert "/ps" in rendered
    assert "/stop" in rendered
    assert "/input-suggestion" in rendered
    assert "/ui" in rendered
    assert "/view [toggle|concise|full]" in rendered
    assert "/compact [focus]" in rendered


def test_ui_slash_command_persists_modern_interface(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\ninterface = \"classic\"\ntheme = \"dark\"\n", encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("ui", "modern"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(interface="classic", theme="dark")),
    )

    assert next_session == "s1"
    assert load_settings(config).ui.interface == "modern"
    assert load_settings(config).ui.theme == "dark"
    assert "Saved UI: Modern UI" in console.export_text()


def test_view_slash_command_toggles_config_and_reports_reasoning_state(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\nview_mode = \"concise\"\n", encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("view", "toggle"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(view_mode="concise")),
    )

    assert next_session == "s1"
    assert load_settings(config).ui.view_mode == "full"
    assert "View: full · reasoning shown" in console.export_text()


def test_view_slash_command_sets_concise_and_reports_hidden_reasoning(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\nview_mode = \"full\"\n", encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("view", "concise"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(view_mode="full")),
    )

    assert next_session == "s1"
    assert load_settings(config).ui.view_mode == "concise"
    assert "View: concise · reasoning hidden" in console.export_text()


def test_view_slash_command_toggles_config_without_argument(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\nview_mode = \"concise\"\n", encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("view"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(view_mode="concise")),
    )

    assert next_session == "s1"
    assert load_settings(config).ui.view_mode == "full"
    assert "View: full · reasoning shown" in console.export_text()


def test_view_slash_command_rejects_invalid_arguments_without_changing_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\nview_mode = \"concise\"\n", encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("view", "thinking"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(view_mode="concise")),
    )

    assert next_session == "s1"
    assert load_settings(config).ui.view_mode == "concise"
    assert "Usage: /view [toggle|concise|full]" in console.export_text()


def test_input_suggestion_slash_command_toggles_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\ninput_suggestions_enabled = true\n", encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("input-suggestion"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(input_suggestions_enabled=True)),
    )

    assert next_session == "s1"
    assert load_settings(config).ui.input_suggestions_enabled is False
    assert "Input suggestions disabled." in console.export_text()


def test_input_suggestion_slash_command_rejects_arguments_without_changing_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[ui]\ninput_suggestions_enabled = false\n", encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("input-suggestion", "on"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(input_suggestions_enabled=False)),
    )

    assert next_session == "s1"
    assert load_settings(config).ui.input_suggestions_enabled is False
    assert "Usage: /input-suggestion" in console.export_text()


def test_mcp_slash_command_shows_no_servers(tmp_path):
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("mcp"), console, tmp_path, "s1")

    assert next_session == "s1"
    assert "MCP: no servers configured." in console.export_text()


def test_mcp_slash_command_shows_active_server_and_preferred_tool(tmp_path):
    console = Console(record=True)

    class FakeRuntime:
        statuses = [
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

    next_session = _handle_slash_command(
        SlashCommand("mcp"),
        console,
        tmp_path,
        "s1",
        mcp_runtime=FakeRuntime(),  # type: ignore[arg-type]
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "tavily (active)" in rendered
    assert "mcp_tavily__tavily_search *web-search*" in rendered


def test_ps_slash_command_shows_no_background_tasks(tmp_path):
    console = Console(record=True)
    manager = BackgroundTaskManager(base_dir=tmp_path / "bg")

    next_session = _handle_slash_command(
        SlashCommand("ps"),
        console,
        tmp_path,
        "s1",
        background_tasks=manager,
    )

    assert next_session == "s1"
    assert "No background tasks." in console.export_text()


def test_ps_and_stop_slash_commands_manage_background_tasks(tmp_path):
    console = Console(record=True)
    manager = BackgroundTaskManager(base_dir=tmp_path / "bg")
    task = manager.start(
        command="sleep",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )

    next_session = _handle_slash_command(
        SlashCommand("ps"),
        console,
        tmp_path,
        "s1",
        background_tasks=manager,
    )
    stopped_session = _handle_slash_command(
        SlashCommand("stop"),
        console,
        tmp_path,
        "s1",
        background_tasks=manager,
    )

    manager.stop_all(force_after_grace=True)
    rendered = console.export_text()
    assert next_session == "s1"
    assert stopped_session == "s1"
    assert task.id in rendered
    assert "running" in rendered
    assert "Stop requested for 1 background task." in rendered


def test_stop_slash_command_can_select_single_background_task(tmp_path):
    console = Console(record=True)
    manager = BackgroundTaskManager(base_dir=tmp_path / "bg")
    first = manager.start(
        command="first",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )
    second = manager.start(
        command="second",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )

    next_session = _handle_slash_command(
        SlashCommand("stop"),
        console,
        tmp_path,
        "s1",
        background_tasks=manager,
        input_func=lambda prompt: second.id,
    )

    manager.wait(second.id, timeout_seconds=1)
    manager.stop_all(force_after_grace=True)
    rendered = console.export_text()
    assert next_session == "s1"
    assert first.id in rendered
    assert second.id in rendered
    assert "3. all" in rendered
    assert "4. cancel" in rendered
    assert f"Stop requested for background task {second.id}." in rendered


def test_stop_slash_command_can_cancel_with_empty_selection(tmp_path):
    console = Console(record=True)
    manager = BackgroundTaskManager(base_dir=tmp_path / "bg")
    manager.start(
        command="first",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )

    next_session = _handle_slash_command(
        SlashCommand("stop"),
        console,
        tmp_path,
        "s1",
        background_tasks=manager,
        input_func=lambda prompt: "",
    )

    manager.stop_all(force_after_grace=True)
    assert next_session == "s1"
    assert "Stop canceled." in console.export_text()


def test_stop_slash_command_can_cancel_with_number_selection(tmp_path):
    console = Console(record=True)
    manager = BackgroundTaskManager(base_dir=tmp_path / "bg")
    manager.start(
        command="first",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )

    next_session = _handle_slash_command(
        SlashCommand("stop"),
        console,
        tmp_path,
        "s1",
        background_tasks=manager,
        input_func=lambda prompt: "3",
    )

    assert next_session == "s1"
    assert manager.running_count() == 1
    manager.stop_all(force_after_grace=True)
    assert "Stop canceled." in console.export_text()


def test_stop_slash_command_accepts_all_argument(tmp_path):
    console = Console(record=True)
    manager = BackgroundTaskManager(base_dir=tmp_path / "bg")
    manager.start(
        command="first",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )
    manager.start(
        command="second",
        argv=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
    )

    next_session = _handle_slash_command(
        SlashCommand("stop", "all"),
        console,
        tmp_path,
        "s1",
        background_tasks=manager,
    )

    assert next_session == "s1"
    assert manager.running_count() == 0
    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(),
        background_tasks=manager,
    )
    assert "bg " not in toolbar
    assert "Stop requested for 2 background tasks." in console.export_text()


def test_run_interactive_init_routes_to_model_prompt(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(
        [
            "/init keep it short",
            CTRL_D_EXIT_CONFIRM_SIGNAL,
            CTRL_D_EXIT_CONFIRM_SIGNAL,
        ]
    )
    captured: list[str] = []

    async def fake_run_once(prompt, **kwargs):
        captured.append(prompt)
        return RunSummary(output="initialized", session_id="init-session", complete=True)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))

    result = terminal.run_interactive(
        Settings(ui=UiConfig(theme="dark", theme_configured=True)),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert len(captured) == 1
    assert f"Target file: {tmp_path.resolve() / 'AGENTS.md'}" in captured[0]
    assert "create the project root AGENTS.md" in captured[0]
    assert "keep it short" in captured[0]
    assert "initialized" in console.export_text()


def test_compact_slash_command_without_active_session(tmp_path):
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("compact"), console, tmp_path, None)

    assert next_session is None
    assert "No active session to compact." in console.export_text()


def test_compact_slash_command_runs_manager_and_reports_success(monkeypatch, tmp_path):
    async def fake_compact_session(self, session_id, *, focus_instruction=None):
        assert session_id == "s1"
        assert focus_instruction == "focus paths"
        return SimpleNamespace(
            compacted=True,
            before_tokens=1000,
            after_tokens=200,
            preserved_item_count=2,
            message="Context compacted.",
        )

    session = DeepySession.create(tmp_path, session_id="s1")
    asyncio.run(session.add_items([{"role": "user", "content": "hello"}]))
    monkeypatch.setattr("deepy.sessions.manager.DeepySessionManager.compact_session", fake_compact_session)
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("compact", "focus paths"),
        console,
        tmp_path,
        "s1",
        settings=Settings(),
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "Compacting context..." in rendered
    assert "Context compacted:" in rendered
    assert "1,000 -> 200 tokens" in rendered


def test_theme_slash_command_shows_and_updates_theme(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "dark"\n', encoding="utf-8")
    console = Console(record=True)

    shown_session = _handle_slash_command(
        SlashCommand("theme"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
        input_func=lambda prompt: "3",
    )
    updated_session = _handle_slash_command(
        SlashCommand("theme", "light"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    rendered = console.export_text()
    assert shown_session == "s1"
    assert updated_session == "s1"
    assert "Current theme: dark" in rendered
    assert "saved:" not in rendered
    assert "resolved:" not in rendered
    assert "Available themes:" in rendered
    assert "Saved UI theme: light" in rendered
    assert "Restart Deepy to apply the theme everywhere." in rendered
    assert 'theme = "light"' in config.read_text(encoding="utf-8")


def test_theme_slash_command_uses_keyboard_picker_when_no_input_func(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "light"\n', encoding="utf-8")
    console = Console(record=True)
    monkeypatch.setattr(terminal, "pick_theme", lambda current: "dark")

    next_session = _handle_slash_command(
        SlashCommand("theme"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="light", theme_configured=True)),
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "Current theme: light" in rendered
    assert "Saved UI theme: dark" in rendered
    assert 'theme = "dark"' in config.read_text(encoding="utf-8")


def test_theme_slash_command_keeps_theme_when_selection_is_empty(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "dark"\n', encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("theme"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
        input_func=lambda prompt: "",
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "Available themes:" in rendered
    assert "Theme unchanged." in rendered
    assert config.read_text(encoding="utf-8") == '[ui]\ntheme = "dark"\n'


def test_theme_slash_command_rejects_invalid_value(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "dark"\n', encoding="utf-8")
    console = Console(record=True)

    next_session = _handle_slash_command(
        SlashCommand("theme", "solarized"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    assert next_session == "s1"
    assert "Usage:" in console.export_text()
    assert config.read_text(encoding="utf-8") == '[ui]\ntheme = "dark"\n'


def test_reset_slash_command_removes_config_and_runs_setup(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "old-key"\n\n[ui]\ntheme = "dark"\n', encoding="utf-8")
    console = Console(record=True)
    answers = iter(["1", "sk-reset", "2", "https://api.deepseek.com", "3", "2"])

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    next_session = _handle_slash_command(
        SlashCommand("reset"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "Removed" in rendered
    assert "config.toml" in rendered
    assert "Starting Deepy configuration setup..." in rendered
    assert "https://platform.deepseek.com/api_keys" in rendered
    assert config.stat().st_mode & 0o777 == 0o600
    text = config.read_text(encoding="utf-8")
    assert "old-key" not in text
    assert 'api_key = "sk-reset"' in text
    assert 'name = "deepseek-v4-flash"' in text
    assert 'theme = "light"' in text


def test_reset_slash_command_prints_xiaomi_api_key_guidance(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "old-key"\n\n[ui]\ntheme = "dark"\n', encoding="utf-8")
    console = Console(record=True)
    answers = iter(["3", "sk-mi-reset", "1", "", "2", "2"])

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    next_session = _handle_slash_command(
        SlashCommand("reset"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "https://platform.xiaomimimo.com/console/api-keys" in rendered
    text = config.read_text(encoding="utf-8")
    assert 'provider = "xiaomi"' in text
    assert 'api_key = "sk-mi-reset"' in text
    assert 'name = "mimo-v2.5-pro"' in text
    assert 'thinking = true' in text
    assert 'reasoning_effort = "enabled"' in text


def test_reset_slash_command_accepts_openrouter_custom_model_and_effort(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "old-key"\n\n[ui]\ntheme = "dark"\n', encoding="utf-8")
    console = Console(record=True)
    answers = iter([
        "2",
        "sk-or-reset",
        "anthropic/claude-sonnet-4.5",
        "",
        "1",
        "minimal",
        "3",
    ])

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    next_session = _handle_slash_command(
        SlashCommand("reset"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    rendered = console.export_text()
    text = config.read_text(encoding="utf-8")
    assert next_session == "s1"
    assert "paste any model name copied from the OpenRouter models page" in rendered
    assert "Reasoning effort:" in rendered
    assert "default" in rendered
    assert "minimal" in rendered
    assert 'provider = "openrouter"' in text
    assert 'api_key = "sk-or-reset"' in text
    assert 'name = "anthropic/claude-sonnet-4.5"' in text
    assert 'reasoning_effort = "minimal"' in text


def test_reset_slash_command_openrouter_disabled_skips_effort_prompt(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "old-key"\n\n[ui]\ntheme = "dark"\n', encoding="utf-8")
    console = Console(record=True)
    answers = iter([
        "2",
        "sk-or-reset",
        "anthropic/claude-sonnet-4.5",
        "",
        "2",
        "3",
    ])

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    next_session = _handle_slash_command(
        SlashCommand("reset"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    rendered = console.export_text()
    text = config.read_text(encoding="utf-8")
    assert next_session == "s1"
    assert "Reasoning effort:" not in rendered
    assert 'thinking = false' in text
    assert 'reasoning_effort = "none"' in text


def test_reset_slash_command_cancellation_restores_existing_config(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    original = '[model]\napi_key = "old-key"\n\n[ui]\ntheme = "dark"\n'
    config.write_text(original, encoding="utf-8")
    console = Console(record=True)
    answers = iter([
        "2",
        "sk-or-reset",
        "anthropic/claude-sonnet-4.5",
        "",
        "1",
    ])

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    next_session = _handle_slash_command(
        SlashCommand("reset"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "Removed" in rendered
    assert "Configuration setup cancelled" in rendered
    assert "Existing config was left unchanged" in rendered
    assert "Traceback" not in rendered
    assert config.read_text(encoding="utf-8") == original


def test_reset_slash_command_cancellation_removes_partial_config_when_none_existed(
    tmp_path,
    monkeypatch,
):
    config = tmp_path / "config.toml"
    console = Console(record=True)
    answers = iter([
        "2",
        "sk-or-reset",
        "anthropic/claude-sonnet-4.5",
        "",
        "1",
    ])

    class FakePromptSession:
        def prompt(self, prompt, default="", is_password=False):
            return next(answers)

    monkeypatch.setattr("prompt_toolkit.PromptSession", FakePromptSession)

    next_session = _handle_slash_command(
        SlashCommand("reset"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, ui=UiConfig(theme="dark", theme_configured=True)),
    )

    rendered = console.export_text()
    assert next_session == "s1"
    assert "No existing config" in rendered
    assert "No config was written" in rendered
    assert "Traceback" not in rendered
    assert not config.exists()


def test_exit_slash_command_prints_exit_summary(tmp_path):
    console = Console(record=True, width=200)

    next_session = _handle_slash_command(
        SlashCommand("exit"),
        console,
        tmp_path,
        None,
        settings=Settings(),
    )

    assert next_session == "__exit__"
    assert "Deepy Session Summary" in console.export_text()


def test_print_usage_footer_shows_known_usage():
    console = Console(record=True)

    _print_usage_footer(
        console,
        RunSummary(
            output="ok",
            session_id="s1",
            complete=True,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=2, total_tokens=12),
        ),
    )

    rendered = console.export_text()
    assert "turn Token Usage input 10 · output 2 · total 12" in rendered


def test_print_usage_footer_shows_turn_duration():
    console = Console(record=True)

    _print_usage_footer(
        console,
        RunSummary(
            output="ok",
            session_id="s1",
            complete=True,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=2, total_tokens=12),
            duration_ms=65_000,
        ),
    )

    assert (
        "turn Token Usage time 1m 5s · input 10 · output 2 · total 12"
        in console.export_text()
    )


def test_working_status_text_shows_elapsed_time_and_interrupt_hint():
    rendered = _working_status_text(time.monotonic(), "Running Read README.md").plain

    assert "Working (0s · esc to interrupt)" in rendered
    assert "Running Read README.md" in rendered


def test_working_status_text_preserves_compact_footer_with_active_work(tmp_path):
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-pro", thinking=True, reasoning_effort="max"),
        ),
        active_work="thinking",
    )

    rendered = _working_status_text(time.monotonic(), "running Read README.md", footer=footer).plain

    assert rendered[0] in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    assert "time 0s" in rendered
    assert "esc to interrupt" in rendered
    assert "running Read README.md" in rendered
    assert "model deepseek-v4-pro[max]" not in rendered
    assert f"cwd {tmp_path}" not in rendered
    assert "ctx unknown/1K" not in rendered
    assert "Working (" not in rendered
    assert "model " not in rendered
    assert "ctx win" not in rendered


def test_local_command_status_text_preserves_compact_footer(tmp_path):
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=2_000, compact_trigger_ratio=0.8)),
        active_work="running local command",
    )

    rendered = terminal._local_command_status_text(
        "printf ok",
        time.monotonic(),
        footer=footer,
    ).plain

    assert "time 0s" in rendered
    assert "esc to interrupt" in rendered
    assert "local command" in rendered
    assert "model deepseek-v4-pro[max]" not in rendered
    assert "ctx unknown/2K" not in rendered
    assert "printf ok" in rendered
    assert "Running local command (" not in rendered


def test_runtime_status_text_uses_segmented_foreground_styles(tmp_path):
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=2_000, compact_trigger_ratio=0.8)),
    )

    rendered = _working_status_text(
        time.monotonic(),
        "Shell",
        footer=footer,
    )

    assert "time 0s · Shell · esc to interrupt" in rendered.plain
    styles = {str(span.style) for span in rendered.spans}
    assert len(styles) >= 4
    assert not any(" on " in style or "bg:" in style for style in styles)


def test_terminal_approval_resolver_clears_status_and_shows_choices(monkeypatch):
    console = Console(record=True)
    stop_status_refresh = threading.Event()
    suspend_interrupt_watcher = threading.Event()
    picker_calls = 0
    picker_kwargs = {}

    class FakeStatus:
        cleared = False

        def clear_for_output(self):
            self.cleared = True

    class FakeThread:
        joined_timeout: float | None = None

        def is_alive(self):
            return True

        def join(self, timeout=None):
            self.joined_timeout = timeout

    def fake_pick_audit_approval(**kwargs):
        nonlocal picker_calls
        picker_calls += 1
        picker_kwargs.update(kwargs)
        assert suspend_interrupt_watcher.is_set()
        return terminal.AUDIT_APPROVAL_APPROVE

    status = FakeStatus()
    status_thread = FakeThread()
    monkeypatch.setattr(terminal, "pick_audit_approval", fake_pick_audit_approval)

    resolver = terminal._terminal_approval_resolver(
        console,
        terminal.DARK_PALETTE,
        status=status,
        stop_status_refresh=stop_status_refresh,
        status_thread_getter=lambda: status_thread,
        suspend_interrupt_watcher=suspend_interrupt_watcher,
    )
    decisions = resolver(
        [
            terminal.PendingApproval(
                index=0,
                name="mcp_tavily",
                tool_name="mcp_tavily__tavily_extract",
                arguments='{"url":"https://example.com"}',
                action_kind="mcp_tool",
                server_name="mcp_tavily",
            )
        ]
    )

    assert stop_status_refresh.is_set()
    assert not suspend_interrupt_watcher.is_set()
    assert status.cleared is True
    assert status_thread.joined_timeout == 0.2
    assert picker_calls == 1
    assert decisions == [terminal.ApprovalDecision(outcome="approve")]
    assert picker_kwargs["can_toggle_preview"] is False
    assert console.export_text() == ""
    rendered = terminal._ANSI_ESCAPE_RE.sub("", picker_kwargs["panel_text_factory"](False))
    assert "Approve MCP tool?" in rendered
    assert "tool: mcp_tavily/mcp_tavily__tavily_extract" in rendered
    assert "url: https://example.com" in rendered
    assert "options:" not in rendered


def test_terminal_approval_panel_renders_shell_summary_without_raw_fields():
    console = Console(record=True, width=120)

    console.print(
        terminal._approval_panel(
            terminal.PendingApproval(
                index=0,
                name="shell",
                tool_name="shell",
                arguments=json_utils.dumps(
                    {
                        "command": "ls /tmp/project",
                        "description": "List project directory.",
                    }
                ),
                action_kind="command",
            ),
            palette=terminal.DARK_PALETTE,
        )
    )

    rendered = console.export_text()
    assert "Approve shell command?" in rendered
    assert "command: ls /tmp/project" in rendered
    assert "description: List project directory." in rendered
    assert "action:" not in rendered
    assert "agent:" not in rendered
    assert "arguments." not in rendered


def test_terminal_approval_panel_renders_mcp_summary_without_raw_json():
    console = Console(record=True, width=120)

    console.print(
        terminal._approval_panel(
            terminal.PendingApproval(
                index=0,
                name="mcp_tavily",
                tool_name="mcp_tavily__tavily_extract",
                arguments=json_utils.dumps(
                    {
                        "urls": ["https://example.com/a", "https://example.com/b"],
                        "format": "markdown",
                    }
                ),
                action_kind="mcp_tool",
                server_name="mcp_tavily",
            ),
            palette=terminal.DARK_PALETTE,
        )
    )

    rendered = console.export_text()
    assert "Approve MCP tool?" in rendered
    assert "tool: mcp_tavily/mcp_tavily__tavily_extract" in rendered
    assert "urls: https://example.com/a, https://example.com/b" in rendered
    assert "format: markdown" in rendered
    assert '{"urls"' not in rendered
    assert "arguments." not in rendered


def test_terminal_approval_panel_renders_write_arguments_as_compact_summary(tmp_path):
    console = Console(record=True, width=120)
    target = tmp_path / "two_sum.py"

    console.print(
        terminal._approval_panel(
            terminal.PendingApproval(
                index=0,
                name="Write",
                tool_name="Write",
                arguments=json_utils.dumps(
                    {
                        "path": str(target),
                        "content": "from typing import List\n\nclass Solution:\n    pass",
                    }
                ),
                action_kind="text_write",
            ),
            palette=terminal.DARK_PALETTE,
            project_root=tmp_path,
        )
    )

    rendered = console.export_text()
    assert "Approve write? two_sum.py" in rendered
    assert "path: two_sum.py" in rendered
    assert "size:" in rendered
    assert "[Write] two_sum.py" not in rendered
    assert "from typing import List" not in rendered
    assert "class Solution:" not in rendered
    assert "\\nclass Solution" not in rendered
    assert "arguments." not in rendered


def test_terminal_approval_panel_renders_update_arguments_as_compact_summary(tmp_path):
    console = Console(record=True, width=120)
    target = tmp_path / "src" / "app.py"

    console.print(
        terminal._approval_panel(
            terminal.PendingApproval(
                index=0,
                name="Update",
                tool_name="Update",
                arguments=json_utils.dumps(
                    {
                        "path": str(target),
                        "old": "value = 1\n",
                        "new": "value = 2\n",
                    }
                ),
                action_kind="text_write",
            ),
            palette=terminal.DARK_PALETTE,
            project_root=tmp_path,
        )
    )

    rendered = console.export_text()
    assert "Approve update? src/app.py" in rendered
    assert "path: src/app.py" in rendered
    assert "edits: 1" in rendered
    assert "[Update] src/app.py" not in rendered
    assert "- value = 1" not in rendered
    assert "+ value = 2" not in rendered


def test_terminal_approval_panel_falls_back_when_update_diff_context_missing(tmp_path):
    console = Console(record=True, width=120)
    target = tmp_path / "src" / "app.py"

    console.print(
        terminal._approval_panel(
            terminal.PendingApproval(
                index=0,
                name="Update",
                tool_name="Update",
                arguments=json_utils.dumps({"path": str(target), "replace_all": True}),
                action_kind="text_write",
            ),
            palette=terminal.DARK_PALETTE,
            project_root=tmp_path,
        )
    )

    rendered = console.export_text()
    assert "Approve update? src/app.py" in rendered
    assert "path: src/app.py" in rendered
    assert "summary:" in rendered
    assert "[Update]" not in rendered


def test_terminal_approval_panel_keeps_outside_project_path_explicit(tmp_path):
    console = Console(record=True, width=120)
    outside = tmp_path.parent / "outside.py"

    console.print(
        terminal._approval_panel(
            terminal.PendingApproval(
                index=0,
                name="Write",
                tool_name="Write",
                arguments=json_utils.dumps({"path": str(outside), "content": "print('x')\n"}),
                action_kind="text_write",
            ),
            palette=terminal.DARK_PALETTE,
            project_root=tmp_path,
        )
    )

    rendered = console.export_text()
    assert f"path: {outside}" in rendered
    assert "path: outside.py" not in rendered


def test_terminal_approval_panel_keeps_file_decision_compact_without_preview(tmp_path):
    console = Console(record=True, width=120)
    content = "\n".join(f"line {index}" for index in range(40)) + "\n"
    item = terminal.PendingApproval(
        index=0,
        name="Write",
        tool_name="Write",
        arguments=json_utils.dumps({"path": str(tmp_path / "long.py"), "content": content}),
        action_kind="text_write",
    )

    panel, can_expand = terminal._approval_panel_state(
        item,
        palette=terminal.DARK_PALETTE,
        project_root=tmp_path,
        expanded=False,
    )
    console.print(panel)
    compact = console.export_text()
    console = Console(record=True, width=120)
    console.print(
        terminal._approval_panel(
            item,
            palette=terminal.DARK_PALETTE,
            project_root=tmp_path,
            expanded=True,
        )
    )
    expanded = console.export_text()

    assert can_expand is False
    assert "review:" not in compact
    assert "line 39" not in compact
    assert "review:" not in expanded
    assert "line 39" not in expanded


def test_terminal_approval_preflight_diff_renders_before_compact_picker(tmp_path, monkeypatch):
    console = Console(record=True, width=120)
    diff = "--- a/long.py\n+++ b/long.py\n@@ -1 +1 @@\n-old\n+new\n"
    item = terminal.PendingApproval(
        index=0,
        name="Write",
        tool_name="Write",
        arguments=json_utils.dumps({"path": str(tmp_path / "long.py"), "content": "new\n"}),
        action_kind="text_write",
        preflight={
            "ok": True,
            "name": "Write",
            "output": "Proposed write",
            "error": None,
            "metadata": {
                "path": str(tmp_path / "long.py"),
                "diff": diff,
                "diff_preview": diff,
                "preflight": True,
            },
        },
    )
    picker_kwargs = {}

    def fake_pick_audit_approval(**kwargs):
        picker_kwargs.update(kwargs)
        return terminal.AUDIT_APPROVAL_APPROVE

    monkeypatch.setattr(terminal, "pick_audit_approval", fake_pick_audit_approval)

    approved = terminal._collect_terminal_approval_decision(
        item,
        console=console,
        palette=terminal.DARK_PALETTE,
        project_root=tmp_path,
        status=None,
        stop_status_refresh=None,
        status_thread_getter=None,
        suspend_interrupt_watcher=None,
    )

    assert approved is True
    rendered = console.export_text()
    assert "• Proposed Change" in rendered
    assert "[Write] long.py" in rendered
    assert "+ new" in rendered
    assert picker_kwargs["can_toggle_preview"] is False
    panel_text_factory = picker_kwargs["panel_text_factory"]
    compact = panel_text_factory(False)
    expanded = panel_text_factory(True)
    compact_plain = terminal._ANSI_ESCAPE_RE.sub("", compact)
    expanded_plain = terminal._ANSI_ESCAPE_RE.sub("", expanded)
    assert compact.count("Approve write? long.py") == 1
    assert expanded.count("Approve write? long.py") == 1
    assert "+ new" not in compact_plain
    assert "+ new" not in expanded_plain


def test_print_stream_event_suppresses_preflight_diff_after_approval(tmp_path):
    console = Console(record=True, width=120)
    diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
    output = {
        "ok": True,
        "name": "Update",
        "output": "Updated file",
        "error": None,
        "metadata": {
            "path": str(tmp_path / "app.py"),
            "diff": diff,
            "diff_preview": diff,
        },
        "awaitUserResponse": False,
    }
    approved_preflight_diffs = {diff}

    _print_stream_event(
        console,
        DeepyStreamEvent(kind="tool_output", text=json_utils.dumps(output)),
        project_root=str(tmp_path),
        approved_preflight_diffs=approved_preflight_diffs,
    )

    rendered = console.export_text()
    assert "[Update]" in rendered
    assert "+ new" not in rendered
    assert approved_preflight_diffs == set()


def test_run_once_with_status_routes_approval_picker_to_main_thread(tmp_path, monkeypatch):
    main_thread = threading.current_thread()
    picker_threads: list[threading.Thread] = []

    class FakeAsyncRunner:
        def submit(self, coroutine):
            future: terminal.Future[RunSummary] = terminal.Future()

            def run() -> None:
                try:
                    future.set_result(asyncio.run(coroutine))
                except BaseException as exc:
                    future.set_exception(exc)

            threading.Thread(target=run, daemon=True).start()
            return future

    def fake_pick_audit_approval(**_kwargs):
        picker_threads.append(threading.current_thread())
        return terminal.AUDIT_APPROVAL_APPROVE

    async def fake_run_once(prompt, **kwargs):
        decisions = kwargs["approval_resolver"](
            [
                terminal.PendingApproval(
                    index=0,
                    name="Write",
                    tool_name="Write",
                    arguments='{"path":"/tmp/out.txt","content":"ok"}',
                    action_kind="text_write",
                )
            ]
        )
        assert threading.current_thread() is not main_thread
        assert decisions[0].outcome == "approve"
        return RunSummary(output=f"answer: {prompt}", session_id="s1", complete=True)

    monkeypatch.setattr(terminal, "pick_audit_approval", fake_pick_audit_approval)

    summary = _run_once_with_status(
        Console(record=True),
        fake_run_once,
        "hello",
        project_root=tmp_path,
        settings=Settings(),
        async_runner=FakeAsyncRunner(),
    )

    assert summary.output == "answer: hello"
    assert picker_threads == [main_thread]


def test_styled_runtime_status_line_preserves_fitted_visible_text():
    fitted = terminal._fit_status_line(
        "⠋ time 0s · Shell · esc to interrupt",
        width=72,
    )

    styled = terminal._style_runtime_status_line(fitted, terminal.DARK_PALETTE)

    assert styled.plain == fitted
    styles = {str(span.style) for span in styled.spans}
    assert len(styles) >= 4
    assert not any(" on " in style or "bg:" in style for style in styles)


def test_runtime_status_spinner_advances_at_refresh_interval(monkeypatch):
    started_at = 100.0
    monkeypatch.setattr(terminal.time, "monotonic", lambda: started_at)

    first = terminal._runtime_spinner_frame(started_at)
    monkeypatch.setattr(terminal.time, "monotonic", lambda: started_at + 1.0)
    second = terminal._runtime_spinner_frame(started_at)

    assert terminal.RUNTIME_STATUS_REFRESH_SECONDS == 1.0
    assert first != second


def test_inline_runtime_status_periodically_refreshes_elapsed_time():
    assert terminal._InlineRuntimeStatus.periodic_refresh is True


def test_status_display_writes_runtime_status_in_output_flow_without_scroll_region(
    tmp_path,
    monkeypatch,
):
    class TtyBuffer(io.StringIO):
        def isatty(self):
            return True

    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-pro", thinking=True, reasoning_effort="max"),
        ),
    )
    buffer = TtyBuffer()
    console = Console(file=buffer, force_terminal=True)
    monkeypatch.setattr(terminal.shutil, "get_terminal_size", lambda fallback: os.terminal_size((80, 24)))

    with terminal._status_display(
        console,
        _working_status_text(time.monotonic(), "thinking", footer=footer),
        palette=terminal.DARK_PALETTE,
    ):
        pass

    output = buffer.getvalue()
    assert output.startswith("\r\x1b[2K")
    assert "\x1b[1;23r" not in output
    assert "\x1b[r" not in output
    assert "\x1b[24;1H" not in output
    assert "\x1b[23;1H" not in output
    assert "model deepseek-v4-pro[max]" not in output
    assert "thinking" in output
    assert "48;2" not in output


def test_status_display_clears_inline_runtime_status_before_output(tmp_path, monkeypatch):
    class TtyBuffer(io.StringIO):
        def isatty(self):
            return True

    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-pro", thinking=True, reasoning_effort="max"),
        ),
    )
    buffer = TtyBuffer()
    console = Console(file=buffer, force_terminal=True)
    monkeypatch.setattr(terminal.shutil, "get_terminal_size", lambda fallback: os.terminal_size((80, 24)))

    with terminal._status_display(
        console,
        _working_status_text(time.monotonic(), "thinking", footer=footer),
        palette=terminal.DARK_PALETTE,
    ) as status:
        renderer = terminal.TerminalStreamRenderer(
            console,
            status=status,
            status_started_at=time.monotonic(),
            footer=footer,
            output_lock=getattr(status, "output_lock", None),
        )
        renderer(DeepyStreamEvent(kind="tool_output", text='{"ok":true,"name":"Read","output":"done"}'))

    output = buffer.getvalue()
    assert "\r\x1b[2K" in output
    assert "\x1b[1;23r" not in output
    assert "\x1b[24;1H" not in output
    assert "thinking" in output
    assert "[Read]" in output


def test_status_display_keeps_inline_runtime_status_for_nonprinting_events(tmp_path, monkeypatch):
    class TtyBuffer(io.StringIO):
        def isatty(self):
            return True

    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-pro", thinking=True, reasoning_effort="max"),
        ),
    )
    buffer = TtyBuffer()
    console = Console(file=buffer, force_terminal=True)
    monkeypatch.setattr(terminal.shutil, "get_terminal_size", lambda fallback: os.terminal_size((80, 24)))

    with terminal._status_display(
        console,
        _working_status_text(time.monotonic(), "status working", footer=footer),
        palette=terminal.DARK_PALETTE,
    ) as status:
        renderer = terminal.TerminalStreamRenderer(
            console,
            status=status,
            status_started_at=time.monotonic(),
            footer=footer,
            output_lock=getattr(status, "output_lock", None),
        )
        before = buffer.getvalue()
        renderer(DeepyStreamEvent(kind="agent_updated"))
        renderer(DeepyStreamEvent(kind="usage"))
        after = buffer.getvalue()

    assert "status working" in before
    assert after == before


def test_runtime_status_line_fits_wide_web_search_text_to_display_cells():
    text = "⠋ time 0s · ↓ 850 tokens · WebSearch · esc to interrupt"

    fitted = terminal._fit_status_line(text, width=56)

    assert cell_len(fitted) == 56
    assert "time 0s" in fitted
    assert "esc to interrupt" in fitted
    assert "WebSearch" in fitted


def test_runtime_status_line_prioritizes_prefix_over_long_tool_payload():
    text = "⠋ time 0s · ↓ 850 tokens · WebSearch · esc to interrupt"

    fitted = terminal._fit_status_line(text, width=56)

    assert cell_len(fitted) == 56
    assert "time 0s" in fitted
    assert "esc to interrupt" in fitted
    assert "WebSearch" in fitted


def test_runtime_status_line_tail_truncates_long_local_command():
    command = "uv run pytest tests/test_terminal_ui.py::test_runtime_status --very-long-option"
    text = f"⠋ time 0s · esc to interrupt · local command · {command}"

    fitted = terminal._fit_status_line(text, width=74)

    assert cell_len(fitted) == 74
    assert "time 0s" in fitted
    assert "esc to interrupt" in fitted
    assert "local command" in fitted
    assert "uv run pytest" in fitted
    assert "--very-long-option" not in fitted
    assert fitted.rstrip().endswith("…")


def test_runtime_status_line_keeps_concise_tool_state_before_interrupt():
    text = "⠋ time 0s · ↓ 850 tokens · Shell · esc to interrupt"

    fitted = terminal._fit_status_line(text, width=66)

    assert cell_len(fitted) == 66
    assert "time 0s" in fitted
    assert "esc to interrupt" in fitted
    assert "Shell" in fitted
    assert fitted.index("Shell") < fitted.index("esc to interrupt")


def test_runtime_status_line_sanitizes_control_sequences_before_fitting():
    text = (
        "⠋ time 0s · esc to interrupt · local command · "
        "printf ok\nBAD\rX\tY \x1b[31mred\x1b[0m\x07"
    )

    fitted = terminal._fit_status_line(text, width=120)
    visible = fitted.rstrip()

    assert cell_len(fitted) == 120
    assert "\n" not in visible
    assert "\r" not in visible
    assert "\t" not in visible
    assert "\x1b" not in visible
    assert "\x07" not in visible
    assert "printf ok BAD X Y red" in visible


def test_runtime_status_line_handles_very_narrow_widths():
    assert terminal._fit_status_line("abcdef", width=1) == "…"
    assert terminal._fit_status_line("abcdef", width=0) == ""


def test_runtime_status_line_pads_shorter_refresh_after_longer_text():
    long_line = terminal._fit_status_line("tool [WebSearch] " + "x" * 80, width=24)
    short_line = terminal._fit_status_line("thinking", width=24)

    assert cell_len(long_line) == 24
    assert cell_len(short_line) == 24
    assert short_line == "thinking" + (" " * 16)


def test_inline_runtime_status_uses_output_lock(monkeypatch):
    class TtyBuffer(io.StringIO):
        def isatty(self):
            return True

    class RecordingLock:
        def __init__(self):
            self.entries = 0

        def __enter__(self):
            self.entries += 1
            return self

        def __exit__(self, *args):
            return None

    lock = RecordingLock()
    buffer = TtyBuffer()
    console = Console(file=buffer, force_terminal=True)
    status = terminal._InlineRuntimeStatus(
        console,
        palette=terminal.DARK_PALETTE,
        output_lock=lock,
    )
    monkeypatch.setattr(terminal.shutil, "get_terminal_size", lambda fallback: os.terminal_size((30, 8)))

    status.update(terminal.Text("tool [WebSearch] DeepSeek 最新模型"))
    status.clear()

    assert lock.entries == 2
    output = buffer.getvalue()
    assert output.startswith("\r\x1b[2K")
    assert "\x1b[8;1H\x1b[2K" not in output


def test_status_display_is_silent_for_recorded_console():
    console = Console(record=True)

    with terminal._status_display(
        console,
        terminal.Text("working"),
        palette=terminal.DARK_PALETTE,
    ):
        pass

    assert console.export_text() == ""


def test_run_once_with_status_passes_interrupt_check(tmp_path):
    observed_interrupt: list[bool] = []

    async def fake_run_once(prompt, **kwargs):
        observed_interrupt.append(kwargs["should_interrupt"]())
        return RunSummary(output=f"answer: {prompt}", session_id="s1", complete=False, interrupted=True)

    summary = _run_once_with_status(
        Console(record=True),
        fake_run_once,
        "hello",
        project_root=tmp_path,
        settings=Settings(),
        should_interrupt=lambda: True,
    )

    assert summary.interrupted is True
    assert observed_interrupt == [True]


def test_format_duration_ms_formats_minutes_and_hours():
    assert _format_duration_ms(352_000) == "5m 52s"
    assert _format_duration_ms(3_660_000) == "1h 1m"


def test_format_token_count_short_uses_compact_units():
    assert _format_token_count_short(999) == "999"
    assert _format_token_count_short(1_100) == "1K"
    assert _format_token_count_short(50_000) == "50K"
    assert _format_token_count_short(838_861) == "839K"
    assert _format_token_count_short(1_048_576) == "1M"
    assert _format_token_count_short(1_500_000) == "1.5M"


def test_format_stream_token_count_short_uses_k_only_units():
    assert _format_stream_token_count_short(999) == "999"
    assert _format_stream_token_count_short(1_100) == "1.1K"
    assert _format_stream_token_count_short(1_048_576) == "1049K"


def test_print_usage_footer_only_shows_turn_usage(tmp_path):
    console = Console(record=True)
    session = DeepySession.create(tmp_path, session_id="s1")
    session._touch_index(active_tokens=900)

    _print_usage_footer(
        console,
        RunSummary(
            output="ok",
            session_id="s1",
            complete=True,
            usage=TokenUsage(
                prompt_tokens=100,
                completion_tokens=2,
                total_tokens=102,
                requests=2,
            ),
        ),
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
        project_root=tmp_path,
    )

    rendered = console.export_text()
    assert "turn Token Usage requests 2 · input 100 · output 2 · total 102" in rendered
    assert "ctx win" not in rendered
    assert "900" not in rendered
    assert "session" not in rendered


def test_format_context_footer_shows_unknown_context_window_without_usage(tmp_path):
    session = DeepySession.create(tmp_path, session_id="s1")
    session._touch_index(active_tokens=200)

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "model deepseek-v4-flash[high]" in toolbar
    assert "model deepseek-v4-flash " not in toolbar
    assert "thinking high" not in toolbar
    assert f"cwd {tmp_path}" in toolbar
    assert "ctx unknown/1K" in toolbar
    assert "ctx win" not in toolbar
    assert "compact ~" not in toolbar
    assert "Enter send" not in toolbar
    assert "Shift+Enter" not in toolbar
    assert "session" not in toolbar
    assert "AGENTS.md loaded" not in toolbar
    assert "Ctrl+D twice exit" not in toolbar


def test_format_context_footer_marks_loaded_agents_md(tmp_path):
    tmp_path.joinpath("AGENTS.md").write_text("Use local rules.", encoding="utf-8")

    toolbar = _format_context_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "[AGENTS.md]" in toolbar
    assert "AGENTS.md loaded" not in toolbar


def test_format_context_footer_ignores_empty_agents_md(tmp_path):
    tmp_path.joinpath("AGENTS.md").write_text("", encoding="utf-8")

    toolbar = _format_context_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "[AGENTS.md]" not in toolbar
    assert "AGENTS.md loaded" not in toolbar


def test_format_context_footer_does_not_use_cumulative_usage_as_context_window(tmp_path):
    session = DeepySession.create(tmp_path, session_id="s1")
    session._touch_index(
        active_tokens=200,
        usage={"prompt_tokens": 900, "completion_tokens": 10, "total_tokens": 910},
    )

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "ctx unknown/1K" in toolbar
    assert "ctx win" not in toolbar
    assert "910" not in toolbar


def test_format_context_footer_shows_latest_request_context_window_only(tmp_path):
    session = DeepySession.create(tmp_path, session_id="s1")
    session._touch_index(
        active_tokens=9_000,
        last_usage_tokens=9_000,
        pending_tokens=0,
        last_usage_record_count=0,
    )
    asyncio.run(session.add_items([{"role": "user", "content": "large prompt"}]))
    session.record_usage({"prompt_tokens": 3_500, "completion_tokens": 10, "total_tokens": 3_510})

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=10_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "ctx 4K/10K (35.1%)" in toolbar
    assert "left" not in toolbar
    assert "ctx win" not in toolbar
    assert "compact ~" not in toolbar
    assert "compact next" not in toolbar


def test_format_context_footer_shows_cache_health(tmp_path):
    session = DeepySession.create(tmp_path, session_id="s1")
    asyncio.run(session.add_items([{"role": "user", "content": "large prompt"}]))
    session.record_usage(
        {
            "prompt_tokens": 3_500,
            "completion_tokens": 10,
            "total_tokens": 3_510,
            "prompt_cache_hit_tokens": 2_800,
            "prompt_cache_miss_tokens": 700,
        }
    )
    session.record_cache_break("prefix changed: tools")

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=10_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "cache 80%" in toolbar
    assert "fresh input 700" not in toolbar
    assert "cached input 2,800" not in toolbar


def test_format_context_footer_marks_next_auto_compact_from_context_window(tmp_path):
    session = DeepySession.create(tmp_path, session_id="s1")
    asyncio.run(session.add_items([{"role": "user", "content": "large prompt"}]))
    session.record_usage({"prompt_tokens": 8_500, "completion_tokens": 10, "total_tokens": 8_510})

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=10_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "ctx 9K/10K (85.1%)" in toolbar
    assert "left" not in toolbar
    assert "ctx win" not in toolbar
    assert "compact next" in toolbar


@pytest.mark.asyncio
async def test_format_context_footer_uses_compacted_context_window_checkpoint(tmp_path):
    session = DeepySession.create(tmp_path, session_id="s1")
    session.record_usage({"prompt_tokens": 8_500, "completion_tokens": 10, "total_tokens": 8_510})
    await session.replace_items([{"role": "user", "content": "summary"}], active_tokens=100)

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=10_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "ctx 100/10K (1.0%)" in toolbar
    assert "left" not in toolbar
    assert "ctx win" not in toolbar
    assert "compact next" not in toolbar


def test_build_status_footer_uses_visual_segments_and_mcp_count(tmp_path):
    tmp_path.joinpath("AGENTS.md").write_text("Use local rules.", encoding="utf-8")
    runtime = SimpleNamespace(active_servers=[object()])

    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-pro", thinking=True, reasoning_effort="max"),
        ),
        mcp_runtime=runtime,
        background_tasks=SimpleNamespace(running_count=lambda: 2),  # type: ignore[arg-type]
        active_work="thinking 3s",
    )

    assert footer.plain.startswith("provider deepseek · thinking 3s · model deepseek-v4-pro[max]")
    assert "mcp 1" in footer.plain
    assert "bg 2" in footer.plain
    assert "[AGENTS.md]" in footer.plain
    assert "MCP" not in footer.plain
    assert "mcp:" not in footer.plain
    assert "AGENTS.md loaded" not in footer.plain
    assert footer.to_prompt_toolkit()[0] == ("class:toolbar.title", "provider")
    assert ("class:toolbar.active", "thinking 3s") in footer.to_prompt_toolkit()
    assert ("class:toolbar.title", "mcp") in footer.to_prompt_toolkit()
    assert ("class:toolbar.title", "bg") in footer.to_prompt_toolkit()
    assert ("class:toolbar.loaded", "[AGENTS.md]") in footer.to_prompt_toolkit()


def test_build_status_footer_shows_startup_ghosts_and_completed_mcp_count(tmp_path):
    startup_state = terminal._StartupState(update_pending=True, mcp_pending=True)
    runtime = SimpleNamespace(active_servers=[])

    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000)),
        mcp_runtime=runtime,
        startup_state=startup_state,
    )

    assert "mcp connecting" in footer.plain
    assert "update checking" in footer.plain

    startup_state.mark_update_complete(None)
    startup_state.mark_mcp_complete()
    runtime.active_servers = [object(), object()]
    footer = _build_status_footer(
        None,
        project_root=tmp_path,
        settings=Settings(context=ContextConfig(window_tokens=1_000)),
        mcp_runtime=runtime,
        startup_state=startup_state,
    )

    assert "mcp 2" in footer.plain
    assert "mcp connecting" not in footer.plain
    assert "update checking" not in footer.plain


def test_run_interactive_renders_welcome_and_prompt_before_delayed_mcp_connect(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    connect_finished = threading.Event()
    observed_toolbars: list[str] = []

    class FakeMcpRuntime:
        active_servers = []
        statuses = []

        def __init__(self, settings, *, project_root):
            pass

        async def connect(self):
            await asyncio.sleep(10)
            connect_finished.set()

        async def cleanup(self):
            pass

    def fake_prompt_for_input(session, **kwargs):
        observed_toolbars.append(_toolbar_text(kwargs["bottom_toolbar"]))
        assert not connect_finished.is_set()
        return "/exit"

    monkeypatch.setattr(terminal, "DeepyMcpRuntime", FakeMcpRuntime)
    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(
        Settings(context=ContextConfig(window_tokens=1_000)),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    assert result == 0
    assert "Deepy" in console.export_text()
    assert any("mcp connecting" in toolbar for toolbar in observed_toolbars)


def test_run_interactive_waits_for_mcp_before_first_model_turn(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["hello", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    events: list[str] = []

    class FakeMcpRuntime:
        active_servers = [object()]
        statuses = []

        def __init__(self, settings, *, project_root):
            pass

        async def connect(self):
            events.append("connect-start")
            await asyncio.sleep(0.05)
            events.append("connect-finish")

        async def cleanup(self):
            events.append("cleanup")

    async def fake_run_once(prompt, **kwargs):
        events.append("run-once")
        return RunSummary(output="ok", session_id="s1", complete=True)

    monkeypatch.setattr(terminal, "DeepyMcpRuntime", FakeMcpRuntime)
    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert events.index("connect-finish") < events.index("run-once")


def test_run_interactive_submits_supported_image_only_prompt_as_attachment(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompt_calls = 0
    captured: list[tuple[str, list[object]]] = []

    def fake_prompt_for_input(session, **kwargs):
        nonlocal prompt_calls
        prompt_calls += 1
        if prompt_calls == 1:
            image_attachments = kwargs["image_attachments"]
            attachment = image_attachments.attach_image(b"image", "image/png")
            return attachment.display_label
        return CTRL_D_EXIT_CONFIRM_SIGNAL

    async def fake_run_once(prompt, **kwargs):
        captured.append((prompt, list(kwargs.get("image_attachments") or [])))
        return RunSummary(output="ok", session_id="s1", complete=True)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(
        Settings(model=ModelConfig(provider="openrouter", name="xiaomi/mimo-v2.5")),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert captured[0][0] == ""
    assert captured[0][1][0].data_url == "data:image/png;base64,aW1hZ2U="
    assert "[图片1]" in console.export_text()


def test_run_interactive_local_command_does_not_wait_for_pending_mcp(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["!printf ok", "/exit"])
    events: list[str] = []

    class FakeMcpRuntime:
        active_servers = []
        statuses = []

        def __init__(self, settings, *, project_root):
            pass

        async def connect(self):
            events.append("connect-start")
            await asyncio.sleep(10)
            events.append("connect-finish")

        async def cleanup(self):
            events.append("cleanup")

    def fake_run_local_command(command, *, cwd, should_interrupt=None):
        events.append("local-command")
        return LocalCommandResult(
            command=command,
            output="ok",
            display_output="ok",
            context_output="ok",
            exit_code=0,
            cwd=cwd,
            shell_path="/bin/sh",
            shell_kind="unknown",
            command_dialect="posix",
            path_style="posix",
            os_family="macos",
            tty_mode="pty",
            duration_ms=1,
            timeout_ms=1000,
        )

    async def fake_run_once(prompt, **kwargs):
        raise AssertionError("local command should not call the model")

    monkeypatch.setattr(terminal, "DeepyMcpRuntime", FakeMcpRuntime)
    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))
    monkeypatch.setattr(terminal, "run_local_command", fake_run_local_command)

    result = terminal.run_interactive(
        Settings(context=ContextConfig(window_tokens=1_000)),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert "local-command" in events
    assert "connect-finish" not in events


def test_run_interactive_shows_fast_version_update_in_welcome(tmp_path, monkeypatch):
    console = Console(record=True, width=160)

    def fake_checker(current_version):
        return terminal.VersionUpdate(
            current_version=current_version,
            latest_version="9.9.9",
            source="PyPI",
            url="https://example.test/deepy",
            install_hint="uv tool upgrade deepy-cli",
        )

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: "/exit")

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        version_update_checker=fake_checker,
    )

    rendered = console.export_text()
    assert result == 0
    assert "9.9.9 available" in rendered
    assert "PyPI" in rendered
    assert "uv tool upgrade deepy-cli" in rendered


def test_run_interactive_prints_delayed_version_update_notice_after_prompt(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    release_update = threading.Event()
    prompts = iter(["", "/exit"])

    def fake_checker(current_version):
        release_update.wait(timeout=1)
        return terminal.VersionUpdate(
            current_version=current_version,
            latest_version="9.9.9",
            source="PyPI",
            url="https://example.test/deepy",
            install_hint="uv tool upgrade deepy-cli",
        )

    def fake_prompt_for_input(session, **kwargs):
        value = next(prompts)
        if value == "":
            release_update.set()
            time.sleep(0.05)
        return value

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        version_update_checker=fake_checker,
    )

    rendered = console.export_text()
    assert result == 0
    assert "Update available:" in rendered
    assert "9.9.9" in rendered


def test_run_interactive_new_session_resets_next_run_session_id(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["first", "/new", "second", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    calls: list[dict[str, object]] = []

    async def fake_run_once(prompt, **kwargs):
        calls.append(
            {
                "prompt": prompt,
                "session_id": kwargs.get("session_id"),
                "background_tasks": isinstance(
                    kwargs.get("background_tasks"),
                    BackgroundTaskManager,
                ),
            }
        )
        session_id = "s1" if prompt == "first" else "s2"
        usage = TokenUsage(
            prompt_tokens=900 if prompt == "first" else 50,
            total_tokens=900 if prompt == "first" else 50,
        )
        DeepySession.create(tmp_path, session_id=session_id).record_usage(usage)
        return RunSummary(output=f"answer {prompt}", session_id=session_id, complete=True, usage=usage)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    toolbars: list[object] = []

    def fake_prompt_for_input(session, **kwargs):
        toolbars.append(kwargs.get("bottom_toolbar"))
        return next(prompts)

    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(
        Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    rendered = console.export_text()
    assert result == 0
    assert calls == [
        {"prompt": "first", "session_id": None, "background_tasks": True},
        {"prompt": "second", "session_id": None, "background_tasks": True},
    ]
    assert "Started a new session." in rendered
    assert "context used" not in rendered
    assert "Enter send" not in str(toolbars)
    assert "/ commands" not in str(toolbars)
    assert "Esc interrupt" not in str(toolbars)
    toolbar_texts = [_toolbar_text(toolbar) for toolbar in toolbars]
    assert "Ctrl+D twice exit" not in str(toolbar_texts)
    assert "model deepseek-v4-pro[max]" in str(toolbar_texts)
    assert "model deepseek-v4-pro " not in str(toolbar_texts)
    assert "thinking max" not in str(toolbar_texts)
    assert f"cwd {tmp_path}" in str(toolbar_texts)
    assert "ctx 900/1K (90.0%) · compact next" in toolbar_texts[1]
    assert "ctx unknown/1K" in toolbar_texts[2]
    assert "ctx 50/1K (5.0%)" in toolbar_texts[3]
    assert "left" not in str(toolbar_texts)
    assert "ctx win" not in str(toolbar_texts)
    assert "compact ~" not in str(toolbar_texts)


def test_run_interactive_local_command_bypasses_model_and_persists_context(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["!printf ok", "normal prompt", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    calls: list[dict[str, object]] = []
    toolbars: list[object] = []

    def fake_prompt_for_input(session, **kwargs):
        toolbars.append(kwargs.get("bottom_toolbar"))
        return next(prompts)

    async def fake_run_once(prompt, **kwargs):
        calls.append({"prompt": prompt, "session_id": kwargs.get("session_id")})
        return RunSummary(
            output="model answer",
            session_id=kwargs.get("session_id") or "model-session",
            complete=True,
        )

    def fake_run_local_command(command, *, cwd, should_interrupt=None):
        return LocalCommandResult(
            command=command,
            output="ok",
            display_output="ok",
            context_output="ok",
            exit_code=0,
            cwd=cwd,
            shell_path="/bin/sh",
            shell_kind="unknown",
            command_dialect="posix",
            path_style="posix",
            os_family="macos",
            tty_mode="pty",
            duration_ms=1,
            timeout_ms=1000,
        )

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)
    monkeypatch.setattr(terminal, "run_local_command", fake_run_local_command)

    result = terminal.run_interactive(
        Settings(context=ContextConfig(window_tokens=2_000, compact_trigger_ratio=0.8)),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    entries = list_session_entries(tmp_path)
    session_id = entries[0].id
    items = asyncio.run(DeepySession.open(tmp_path, session_id).get_items())
    rendered = console.export_text()

    assert result == 0
    assert calls == [{"prompt": "normal prompt", "session_id": session_id}]
    assert items[0] == {"role": "user", "content": "!printf ok"}
    assert items[1]["type"] == "function_call"
    assert items[1]["name"] == "shell"
    assert items[2]["type"] == "function_call_output"
    assert "ok" in rendered
    assert "ctx unknown/2K" in _toolbar_text(toolbars[0])
    assert "ctx " in _toolbar_text(toolbars[1])
    assert "ctx win" not in "".join(_toolbar_text(toolbar) for toolbar in toolbars)


def test_run_interactive_local_command_renders_sanitized_windows_output(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["!echo dirty", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    def fake_prompt_for_input(session, **kwargs):
        return next(prompts)

    def fake_run_local_command(command, *, cwd, should_interrupt=None):
        return LocalCommandResult(
            command=command,
            output="\x1b[31m中文\x1b[0m\r\nnext\x01",
            display_output="\x1b[31m中文\x1b[0m\r\nnext\x01",
            context_output="\x1b[31m中文\x1b[0m\r\nnext\x01",
            exit_code=0,
            cwd=cwd,
            shell_path="powershell.exe",
            shell_kind="powershell",
            command_dialect="powershell",
            path_style="windows",
            os_family="windows",
            tty_mode="pipe",
            duration_ms=1,
            timeout_ms=1000,
        )

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)
    monkeypatch.setattr(terminal, "run_local_command", fake_run_local_command)

    result = terminal.run_interactive(
        Settings(context=ContextConfig(window_tokens=2_000, compact_trigger_ratio=0.8)),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    rendered = console.export_text()
    assert result == 0
    assert "中文" in rendered
    assert "next" in rendered
    assert "\x1b" not in rendered
    assert "[31m" not in rendered


def test_run_interactive_empty_local_command_does_not_append_or_call_model(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["!", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    async def fake_run_once(prompt, **kwargs):
        raise AssertionError("empty local command should not call run_once")

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))

    result = terminal.run_interactive(
        Settings(context=ContextConfig(window_tokens=2_000, compact_trigger_ratio=0.8)),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert "Usage: !<command>" in console.export_text()
    assert list_session_entries(tmp_path) == []


def test_run_interactive_handles_multiple_pending_question_rounds(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["start", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    calls: list[dict[str, object]] = []
    collected_questions: list[str] = []
    status_calls = 0

    async def fake_run_once(prompt, **kwargs):
        calls.append({"prompt": prompt, "session_id": kwargs.get("session_id")})
        if len(calls) == 1:
            return RunSummary(
                output="",
                session_id="s1",
                complete=False,
                status="waiting_for_user",
                pending_questions=[{"question": "First?", "options": [{"label": "Yes"}]}],
            )
        if len(calls) == 2:
            return RunSummary(
                output="",
                session_id="s1",
                complete=False,
                status="waiting_for_user",
                pending_questions=[{"question": "Second?", "options": [{"label": "No"}]}],
            )
        return RunSummary(output="done", session_id="s1", complete=True)

    def fake_collect(console, pending_questions):
        collected_questions.append(pending_questions[0]["question"])
        return f"answer for {pending_questions[0]['question']}"

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))
    monkeypatch.setattr(terminal, "_collect_pending_question_response", fake_collect)

    def fake_status_display(console, initial_status, *, palette):
        nonlocal status_calls
        status_calls += 1
        return _FakeStatusDisplay()

    monkeypatch.setattr(terminal, "_status_display", fake_status_display)

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert collected_questions == ["First?", "Second?"]
    assert [call["session_id"] for call in calls] == [None, "s1", "s1"]
    assert [call["prompt"] for call in calls] == ["start", "answer for First?", "answer for Second?"]
    assert status_calls == 3
    rendered = console.export_text()
    assert "done" in rendered
    assert "> answer for First?" not in rendered
    assert "> answer for Second?" not in rendered


def test_run_interactive_stops_pending_question_loop_at_limit(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["start", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    calls: list[object] = []

    async def fake_run_once(prompt, **kwargs):
        calls.append(prompt)
        return RunSummary(
            output="",
            session_id="s1",
            complete=False,
            status="waiting_for_user",
            pending_questions=[{"question": "Again?", "options": [{"label": "Yes"}]}],
        )

    monkeypatch.setattr(terminal, "MAX_CLARIFICATION_ROUNDS_PER_TURN", 1)
    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))
    monkeypatch.setattr(
        terminal,
        "_collect_pending_question_response",
        lambda console, pending_questions: "answer",
    )

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert calls == ["start", "answer"]
    assert "Stopped after 1 clarification rounds." in console.export_text()


def test_run_interactive_reloads_settings_after_model_change(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key = "sk-test"\nname = "deepseek-v4-pro"\nthinking = true\nreasoning_effort = "max"\n'
        '\n[ui]\ntheme = "dark"\n',
        encoding="utf-8",
    )
    console = Console(record=True, width=160)
    prompts = iter(["/model set deepseek-v4-flash high", "hello", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    observed: list[tuple[str, str]] = []

    async def fake_run_once(prompt, **kwargs):
        settings = kwargs["settings"]
        observed.append((settings.model.name, settings.model.reasoning_mode))
        return RunSummary(output=f"answer {prompt}", session_id="s1", complete=True)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))

    result = terminal.run_interactive(
        Settings(
            path=config,
            model=ModelConfig(api_key="sk-test", name="deepseek-v4-pro"),
            ui=UiConfig(theme="dark", theme_configured=True),
        ),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert observed == [("deepseek-v4-flash", "high")]


def test_run_interactive_refreshes_skill_completion_after_market_install(tmp_path, monkeypatch):
    home = tmp_path / "home"
    console = Console(record=True, width=160)
    prompts = iter(
        [
            "/skills install demo",
            CTRL_D_EXIT_CONFIRM_SIGNAL,
            CTRL_D_EXIT_CONFIRM_SIGNAL,
        ]
    )
    slash_command_labels: list[list[str]] = []

    def fake_create_prompt_session(**kwargs):
        slash_command_labels.append([item.label for item in kwargs["slash_commands"]])
        return object()

    def fake_install_market_skill(name):
        skill_dir = home / ".agents" / "skills" / name
        skill_dir.mkdir(parents=True)
        skill_dir.joinpath("SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Demo skill\n---\nUse demo.",
            encoding="utf-8",
        )
        return SimpleNamespace(name=name, install_path=skill_dir)

    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(terminal, "create_prompt_session", fake_create_prompt_session)
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))
    monkeypatch.setattr(terminal, "install_market_skill", fake_install_market_skill)

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    assert result == 0
    assert "/demo" not in slash_command_labels[0]
    assert "/demo" in slash_command_labels[1]
    assert "Installed skill: demo" in console.export_text()


def test_run_interactive_subagent_slash_command_routes_model_turn(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(
        [
            "/tester run focused tests",
            CTRL_D_EXIT_CONFIRM_SIGNAL,
            CTRL_D_EXIT_CONFIRM_SIGNAL,
        ]
    )
    calls: list[tuple[str, list[str]]] = []

    async def fake_run_once(prompt: str, **kwargs):
        calls.append((prompt, kwargs["skill_names"]))
        return RunSummary(output="ok", session_id="s1", complete=True)

    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(prompts))

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    assert result == 0
    assert calls == [(build_subagent_slash_prompt("tester", "run focused tests"), [])]


def test_print_stream_event_suppresses_usage_event_to_avoid_duplicate_footer():
    console = Console(record=True)

    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="usage",
            payload={
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "completion_tokens_details": {"reasoning_tokens": 1},
                }
            },
        ),
    )

    assert console.export_text() == ""


def test_print_assistant_output_renders_markdown():
    console = Console(record=True, width=120)

    _print_assistant_output(
        console,
        "**Deepy** 项目\n\n- 终端 Agent\n\n```bash\nuv run deepy --help\n```",
    )

    rendered = console.export_text()
    assert "• [Assistant]" in rendered
    assert "Deepy" in rendered
    assert "**Deepy**" not in rendered
    assert "• 终端 Agent" in rendered
    assert "uv run deepy --help" in rendered
    assert "```" not in rendered


def test_print_assistant_output_shows_status_while_rendering(monkeypatch):
    class TtyBuffer(io.StringIO):
        def isatty(self):
            return True

    buffer = TtyBuffer()
    console = Console(file=buffer, force_terminal=True, width=120)

    def fake_render_markdown(text, *, palette, width):
        assert "rendering response" in buffer.getvalue()
        return terminal.Text("rendered response")

    monkeypatch.setattr(terminal, "render_markdown", fake_render_markdown)

    _print_assistant_output(console, "**Deepy**")

    output = buffer.getvalue()
    assert "rendering response" in output
    assert "[Assistant]" in output
    assert "rendered response" in output
    assert "\x1b[1;23r" not in output


def test_run_once_with_status_returns_summary(tmp_path):
    async def fake_run_once(prompt, **kwargs):
        return RunSummary(output=f"answer: {prompt}", session_id="s1", complete=True)

    summary = _run_once_with_status(
        Console(record=True),
        fake_run_once,
        "hello",
        project_root=tmp_path,
        settings=Settings(),
    )

    assert summary.output == "answer: hello"


def test_run_interactive_requires_two_ctrl_d_to_exit(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events = iter([CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    def fake_prompt_for_input(session, **kwargs):
        return next(events)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    rendered = console.export_text()
    assert result == 0
    assert "Press Ctrl+D again to exit." in rendered
    assert "Deepy Session Summary" in rendered


def test_run_interactive_exit_stops_background_tasks_before_mcp_cleanup(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events: list[str] = []

    class FakeBackgroundTaskManager:
        def __init__(self):
            self.running = 1

        def running_count(self):
            return self.running

        def stop_all(self, *, force_after_grace=True):
            events.append("stop_all")
            self.running = 0
            return SimpleNamespace(stopped=(object(),))

        def list(self, *, active_only=False):
            return []

    class FakeMcpRuntime:
        active_servers = []
        statuses = []

        def __init__(self, settings, *, project_root):
            pass

        async def connect(self):
            events.append("connect")

        async def cleanup(self):
            events.append("cleanup")

    monkeypatch.setattr(terminal, "BackgroundTaskManager", FakeBackgroundTaskManager)
    monkeypatch.setattr(terminal, "DeepyMcpRuntime", FakeMcpRuntime)
    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: "/exit")

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    assert result == 0
    assert events == ["connect", "stop_all", "cleanup"]
    assert "Stopped 1 background task." in console.export_text()


def test_run_interactive_exit_summary_includes_session_cost(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events = iter(["hello", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    balances = iter(
        [
            BalanceStatus(
                is_available=True,
                balance_infos=(
                    BalanceInfo("CNY", "100.00", "0.00", "100.00"),
                ),
            ),
            BalanceStatus(
                is_available=True,
                balance_infos=(
                    BalanceInfo("CNY", "99.75", "0.00", "99.75"),
                ),
            ),
        ]
    )

    async def fake_run_once(prompt, **kwargs):
        return RunSummary(output="ok", session_id="s1", complete=True)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(terminal, "fetch_deepseek_balance", lambda settings: next(balances))

    result = terminal.run_interactive(
        Settings(model=ModelConfig(api_key="sk-test")),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    rendered = console.export_text()
    assert result == 0
    assert "session cost" in rendered
    assert "CNY 0.25" in rendered
    assert "DeepSeek balance delta" in rendered


def test_run_interactive_exit_summary_shows_cost_unavailable(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events = iter(["hello", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    balances = iter(
        [
            BalanceStatus(
                is_available=True,
                balance_infos=(
                    BalanceInfo("CNY", "100.00", "0.00", "100.00"),
                ),
            ),
            BalanceStatus(unavailable_reason="timeout"),
        ]
    )

    async def fake_run_once(prompt, **kwargs):
        return RunSummary(output="ok", session_id="s1", complete=True)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(terminal, "fetch_deepseek_balance", lambda settings: next(balances))

    result = terminal.run_interactive(
        Settings(model=ModelConfig(api_key="sk-test")),
        project_root=tmp_path,
        console=console,
        run_once=fake_run_once,
        version_update_checker=None,
    )

    rendered = console.export_text()
    assert result == 0
    assert "session cost" in rendered
    assert "unavailable (end timeout)" in rendered


def test_run_interactive_exit_summary_marks_third_party_cost_unsupported(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events = iter([CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    def fail_fetch(settings):
        raise AssertionError("balance lookup should not run")

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(terminal, "fetch_deepseek_balance", fail_fetch)

    result = terminal.run_interactive(
        Settings(
            model=ModelConfig(
                provider="openrouter",
                name="xiaomi/mimo-v2.5-pro",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-test",
            )
        ),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    rendered = console.export_text()
    assert result == 0
    assert "session cost" in rendered
    assert "unsupported" in rendered


def test_stable_non_status_exit_does_not_fetch_balance(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events = iter([CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    def fail_fetch(settings):
        raise AssertionError("balance lookup should not run")

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(terminal, "fetch_deepseek_balance", fail_fetch)

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    assert result == 0
    assert "Deepy Session Summary" in console.export_text()


def test_run_interactive_prompts_for_missing_theme_before_welcome(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")
    console = Console(record=True, width=160)
    events = iter([CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(terminal, "_prompt_theme_choice", lambda default="dark": "light")

    result = terminal.run_interactive(
        Settings(path=config, ui=UiConfig(theme="dark", theme_configured=False)),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    assert result == 0
    rendered = console.export_text()
    assert "Theme" in rendered
    assert "light" in rendered
    assert 'theme = "light"' in config.read_text(encoding="utf-8")


def test_run_interactive_prompts_for_theme_when_config_file_is_missing(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    console = Console(record=True, width=160)
    events = iter([CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(terminal, "_prompt_theme_choice", lambda default="dark": "dark")

    result = terminal.run_interactive(
        Settings(path=config, ui=UiConfig(theme="dark", theme_configured=False)),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    assert result == 0
    assert 'theme = "dark"' in config.read_text(encoding="utf-8")


def test_run_interactive_skips_theme_prompt_when_theme_exists(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[ui]\ntheme = "light"\n', encoding="utf-8")
    console = Console(record=True, width=160)
    events = iter([CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(
        terminal,
        "_prompt_theme_choice",
        lambda default="dark": (_ for _ in ()).throw(AssertionError("unexpected theme prompt")),
    )

    result = terminal.run_interactive(
        Settings(path=config, ui=UiConfig(theme="light", theme_configured=True)),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    assert result == 0
    assert "Theme" in console.export_text()


def test_run_interactive_resets_ctrl_d_exit_confirmation_after_input(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events = iter(
        [
            CTRL_D_EXIT_CONFIRM_SIGNAL,
            "",
            CTRL_D_EXIT_CONFIRM_SIGNAL,
            CTRL_D_EXIT_CONFIRM_SIGNAL,
        ]
    )
    calls = 0

    def fake_prompt_for_input(session, **kwargs):
        nonlocal calls
        calls += 1
        return next(events)

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(
        Settings(),
        project_root=tmp_path,
        console=console,
        version_update_checker=None,
    )

    rendered = console.export_text()
    assert result == 0
    assert calls == 4
    assert rendered.count("Press Ctrl+D again to exit.") == 2
    assert "Deepy Session Summary" in rendered
