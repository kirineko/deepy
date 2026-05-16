from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
from rich.console import Console

from deepy.config import ContextConfig, ModelConfig, Settings, UiConfig
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.mcp import McpServerStatus
from deepy.sessions import DeepyJsonlSession, SessionEntry, list_session_entries
from deepy.skill_market import MarketSkill
from deepy.usage import TokenUsage
import deepy.ui.terminal as terminal
from deepy.ui import SlashCommand, parse_slash_command
from deepy.ui.local_command import LocalCommandResult
from deepy.ui.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.skill_picker import SkillMenuAction
from deepy.ui.terminal import _collect_pending_question_response
from deepy.ui.terminal import _format_context_footer
from deepy.ui.terminal import _handle_slash_command
from deepy.ui.terminal import _print_assistant_output
from deepy.ui.terminal import _print_stream_event
from deepy.ui.terminal import _print_user_input
from deepy.ui.terminal import _print_usage_footer
from deepy.ui.terminal import _format_duration_ms
from deepy.ui.terminal import _format_token_count_short
from deepy.ui.terminal import _tool_output_text
from deepy.ui.terminal import _run_once_with_status
from deepy.ui.terminal import _working_status_text
from deepy.utils import json as json_utils


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
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
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
                    "name": "read",
                    "arguments": '{"file_path":"README.md"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": '{"ok":true,"name":"read","output":"","metadata":{"path":"README.md"}}',
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
            name="read",
            payload={"call_id": "call-1", "arguments": '{"file_path":"/repo/README.md"}'},
        ),
        project_root="/repo",
        pending_tool_calls=pending,
    )
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            payload={"call_id": "call-1"},
            text='{"ok":true,"name":"read","output":"","error":null,"metadata":{"path":"/tmp/a"}}',
        ),
        pending_tool_calls=pending,
    )

    rendered = console.export_text()
    assert "[Read] README.md  ok" in rendered
    assert "tool call:" not in rendered
    assert "tool output:" not in rendered


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
        "name": "edit",
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
    )

    rendered = console.export_text()
    assert "[Modify]  ok" in rendered
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
        "name": "write",
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
    assert "[Write]  ok" in rendered
    assert "[Write] /repo/src/lib.rs (+1 -0)" in rendered
    assert "new file body" in rendered
    assert "+new file body" not in rendered
    assert "Edited" not in rendered


def test_print_stream_event_passes_console_width_to_diff_preview(monkeypatch):
    console = Console(record=True, width=72)
    captured: dict[str, int | None] = {}
    output = {
        "ok": True,
        "name": "edit",
        "output": "Edited file",
        "error": None,
        "metadata": {
            "path": "/repo/src/lib.rs",
            "diff": "--- a//repo/src/lib.rs\n+++ b//repo/src/lib.rs\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        },
        "awaitUserResponse": False,
    }

    def fake_render_tool_diff_preview(text, *, palette=None, width=None):
        del text, palette
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
            name="write",
            payload={
                "call_id": "call-1",
                "arguments": json_utils.dumps(
                    {
                        "file_path": "/repo/src/lib.rs",
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
                    "name": "write",
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
    assert "[Write] src/lib.rs (4 lines, 34 chars)  ok" in rendered
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


def test_terminal_stream_renderer_flushes_reasoning_summary():
    console = Console(record=True)
    renderer = terminal.TerminalStreamRenderer(console)

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="让我先看看项目结构。"))
    renderer.flush()

    rendered = console.export_text()
    assert "Thinking" in rendered
    assert "让我先看看项目结构。" in rendered


def test_terminal_stream_renderer_flushes_reasoning_for_each_model_turn():
    console = Console(record=True)
    renderer = terminal.TerminalStreamRenderer(console)

    renderer(DeepyStreamEvent(kind="reasoning_delta", text="第一轮思考。"))
    renderer.flush()
    renderer(DeepyStreamEvent(kind="reasoning_delta", text="第二轮思考。"))
    renderer.flush()

    rendered = console.export_text()
    assert "第一轮思考。" in rendered
    assert "第二轮思考。" in rendered


def test_terminal_stream_renderer_flushes_full_reasoning_without_truncation():
    console = Console(record=True, width=120)
    renderer = terminal.TerminalStreamRenderer(console)
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


def test_status_slash_command_prints_status(tmp_path):
    console = Console(record=True, width=200)

    next_session = _handle_slash_command(SlashCommand("status"), console, tmp_path, "s1")

    assert next_session == "s1"
    assert f"Project: {tmp_path}" in console.export_text()


def test_model_slash_command_lists_models(tmp_path):
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("model", "list"), console, tmp_path, "s1")

    rendered = console.export_text()
    assert next_session == "s1"
    assert "Available models:" in rendered
    assert "deepseek-v4-pro" in rendered
    assert "deepseek-v4-flash" in rendered
    assert "Reasoning modes:" in rendered
    assert "none" in rendered
    assert "high" in rendered
    assert "max" in rendered


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
    assert "Saved model: deepseek-v4-flash · reasoning: high" in rendered
    assert 'api_key = "sk-test"' in text
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
    assert "Saved model: deepseek-v4-pro · reasoning: none" in console.export_text()
    assert 'thinking = false' in config.read_text(encoding="utf-8")


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
    answers = iter(["2", "1"])

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
    assert "Current model: deepseek-v4-pro · reasoning: max" in rendered
    assert "Available models:" in rendered
    assert "Thinking strength:" in rendered
    assert "Saved model: deepseek-v4-flash · reasoning: none" in rendered
    assert 'name = "deepseek-v4-flash"' in text
    assert 'thinking = false' in text


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
    monkeypatch.setattr(terminal, "pick_model", lambda current: "deepseek-v4-flash")
    monkeypatch.setattr(terminal, "pick_reasoning_mode", lambda current: "high")

    next_session = _handle_slash_command(
        SlashCommand("model"),
        console,
        tmp_path,
        "s1",
        settings=Settings(path=config, model=ModelConfig(name="deepseek-v4-pro")),
    )

    text = config.read_text(encoding="utf-8")
    assert next_session == "s1"
    assert "Saved model: deepseek-v4-flash · reasoning: high" in console.export_text()
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
    assert "/compact [focus]" in rendered


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

    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
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
    answers = iter(["sk-reset", "deepseek-v4-flash", "https://api.deepseek.com", "3"])

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
    assert "Goodbye!" in console.export_text()


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
    rendered = _working_status_text(time.monotonic(), "Running read README.md").plain

    assert "Working (0s · esc to interrupt)" in rendered
    assert "Running read README.md" in rendered


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
    assert _format_token_count_short(50_000) == "50K"
    assert _format_token_count_short(838_861) == "839K"
    assert _format_token_count_short(1_048_576) == "1M"
    assert _format_token_count_short(1_500_000) == "1.5M"


def test_print_usage_footer_only_shows_turn_usage(tmp_path):
    console = Console(record=True)
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
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
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    session._touch_index(active_tokens=200)

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "model deepseek-v4-flash" in toolbar
    assert "thinking high" in toolbar
    assert f"cwd {tmp_path}" in toolbar
    assert "ctx win unknown/1K" in toolbar
    assert "compact ~" not in toolbar
    assert "Enter send" not in toolbar
    assert "Shift+Enter" not in toolbar
    assert "session" not in toolbar
    assert "AGENTS.md loaded" not in toolbar


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

    assert "AGENTS.md loaded" in toolbar


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

    assert "AGENTS.md loaded" not in toolbar


def test_format_context_footer_does_not_use_cumulative_usage_as_context_window(tmp_path):
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
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

    assert "ctx win unknown/1K" in toolbar
    assert "910" not in toolbar


def test_format_context_footer_shows_latest_request_context_window_only(tmp_path):
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    session._touch_index(
        active_tokens=9_000,
        last_usage_tokens=9_000,
        pending_tokens=0,
        last_usage_record_count=0,
    )
    session.path.parent.mkdir(parents=True, exist_ok=True)
    session.path.write_text(
        '{"role":"user","content":"large prompt","meta":{"sdk_item":{"role":"user","content":"large prompt"}}}\n',
        encoding="utf-8",
    )
    session.record_usage({"prompt_tokens": 3_500, "completion_tokens": 10, "total_tokens": 3_510})

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=10_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "ctx win 4K/10K (35.1%, 6K left)" in toolbar
    assert "compact ~" not in toolbar
    assert "compact next" not in toolbar


def test_format_context_footer_marks_next_auto_compact_from_context_window(tmp_path):
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    session.path.parent.mkdir(parents=True, exist_ok=True)
    session.path.write_text(
        '{"role":"user","content":"large prompt","meta":{"sdk_item":{"role":"user","content":"large prompt"}}}\n',
        encoding="utf-8",
    )
    session.record_usage({"prompt_tokens": 8_500, "completion_tokens": 10, "total_tokens": 8_510})

    toolbar = _format_context_footer(
        "s1",
        project_root=tmp_path,
        settings=Settings(
            context=ContextConfig(window_tokens=10_000, compact_trigger_ratio=0.8),
            model=ModelConfig(name="deepseek-v4-flash", thinking=True, reasoning_effort="high"),
        ),
    )

    assert "ctx win 9K/10K (85.1%, 1K left)" in toolbar
    assert "compact next" in toolbar


@pytest.mark.asyncio
async def test_format_context_footer_uses_compacted_context_window_checkpoint(tmp_path):
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
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

    assert "ctx win 100/10K (1.0%, 10K left)" in toolbar
    assert "compact next" not in toolbar


def test_run_interactive_new_session_resets_next_run_session_id(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    prompts = iter(["first", "/new", "second", CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])
    calls: list[dict[str, object]] = []

    async def fake_run_once(prompt, **kwargs):
        calls.append({"prompt": prompt, "session_id": kwargs.get("session_id")})
        session_id = "s1" if prompt == "first" else "s2"
        usage = TokenUsage(
            prompt_tokens=900 if prompt == "first" else 50,
            total_tokens=900 if prompt == "first" else 50,
        )
        DeepyJsonlSession.create(tmp_path, session_id=session_id).record_usage(usage)
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
        {"prompt": "first", "session_id": None},
        {"prompt": "second", "session_id": None},
    ]
    assert "Started a new session." in rendered
    assert "context used" not in rendered
    assert "Enter send" not in str(toolbars)
    assert "/ commands" not in str(toolbars)
    assert "Esc interrupt" not in str(toolbars)
    toolbar_texts = [str(toolbar) for toolbar in toolbars]
    assert "Ctrl+D twice exit" in str(toolbar_texts)
    assert "model deepseek-v4-pro" in str(toolbar_texts)
    assert "thinking max" in str(toolbar_texts)
    assert f"cwd {tmp_path}" in str(toolbar_texts)
    assert "ctx win 900/1K (90.0%, 100 left) · compact next" in toolbar_texts[1]
    assert "ctx win unknown/1K" in toolbar_texts[2]
    assert "ctx win 50/1K (5.0%, 950 left)" in toolbar_texts[3]
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
    items = asyncio.run(DeepyJsonlSession.open(tmp_path, session_id).get_items())
    rendered = console.export_text()

    assert result == 0
    assert calls == [{"prompt": "normal prompt", "session_id": session_id}]
    assert items[0] == {"role": "user", "content": "!printf ok"}
    assert items[1]["type"] == "function_call"
    assert items[1]["name"] == "shell"
    assert items[2]["type"] == "function_call_output"
    assert "ok" in rendered
    assert "ctx win unknown/2K" in str(toolbars[0])
    assert "ctx win " in str(toolbars[1])


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
    assert "/skill:demo" not in slash_command_labels[0]
    assert "/skill:demo" in slash_command_labels[1]
    assert "Installed skill: demo" in console.export_text()


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
    assert "Deepy" in rendered
    assert "**Deepy**" not in rendered
    assert "• 终端 Agent" in rendered
    assert "code bash" in rendered
    assert "```" not in rendered


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


def test_run_interactive_prompts_for_missing_theme_before_welcome(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[model]\napi_key = "sk-test"\n', encoding="utf-8")
    console = Console(record=True, width=160)
    events = iter([CTRL_D_EXIT_CONFIRM_SIGNAL, CTRL_D_EXIT_CONFIRM_SIGNAL])

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", lambda session, **kwargs: next(events))
    monkeypatch.setattr(terminal, "_prompt_theme_choice", lambda default="auto": "light")

    result = terminal.run_interactive(
        Settings(path=config, ui=UiConfig(theme="auto", theme_configured=False)),
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
    monkeypatch.setattr(terminal, "_prompt_theme_choice", lambda default="auto": "dark")

    result = terminal.run_interactive(
        Settings(path=config, ui=UiConfig(theme="auto", theme_configured=False)),
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
        lambda default="auto": (_ for _ in ()).throw(AssertionError("unexpected theme prompt")),
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
