from __future__ import annotations

import asyncio

from rich.console import Console

from deepy.config import ContextConfig, Settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary
from deepy.sessions import DeepyJsonlSession, SessionEntry
from deepy.usage import TokenUsage
import deepy.ui.terminal as terminal
from deepy.ui import SlashCommand, parse_slash_command
from deepy.ui.terminal import _collect_pending_question_response
from deepy.ui.terminal import _handle_slash_command
from deepy.ui.terminal import _print_assistant_output
from deepy.ui.terminal import _print_stream_event
from deepy.ui.terminal import _print_user_input
from deepy.ui.terminal import _print_usage_footer
from deepy.ui.terminal import _run_once_with_status
from deepy.utils import json as json_utils


def test_parse_slash_command_handles_argument():
    assert parse_slash_command("/resume abc123") == SlashCommand("resume", "abc123")


def test_parse_slash_command_ignores_regular_prompt():
    assert parse_slash_command("please edit this") is None


def test_parse_slash_command_strips_whitespace():
    assert parse_slash_command("  /exit  ") == SlashCommand("exit", "")


def test_skills_slash_command_lists_project_skills(tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n",
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("skills"), console, tmp_path, "s1")

    assert next_session == "s1"
    rendered = console.export_text()
    assert "Project skills:" in rendered
    assert "demo - Demo skill" in rendered


def test_skill_slash_command_prints_skill_body(tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Body\nUse this skill.",
        encoding="utf-8",
    )
    console = Console(record=True)

    next_session = _handle_slash_command(SlashCommand("skill", "demo"), console, tmp_path, "s1")

    assert next_session == "s1"
    assert "Use this skill." in console.export_text()


def test_use_slash_command_loads_skill_name(tmp_path):
    skill_dir = tmp_path / ".deepy" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\nUse this skill.",
        encoding="utf-8",
    )
    console = Console(record=True)
    loaded: list[str] = []

    next_session = _handle_slash_command(SlashCommand("use", "demo"), console, tmp_path, "s1", loaded)

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
    assert "read README.md  ok" in rendered
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
    response = _collect_pending_question_response(
        Console(record=True),
        [
            {
                "question": "Which scopes?",
                "multiSelect": True,
                "options": [{"label": "tests"}, {"label": "docs"}],
            }
        ],
        input_func=lambda prompt: "1, lint",
    )

    assert '"Which scopes?"="tests, lint"' in response


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
    assert "read README.md  ok" in rendered
    assert "tool call:" not in rendered
    assert "tool output:" not in rendered


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
    assert "edit  ok" in rendered
    assert "old" in rendered
    assert "new" in rendered
    assert "same" in rendered
    assert "---" not in rendered
    assert "+++" not in rendered
    assert "@@" not in rendered
    assert "-old" not in rendered
    assert "+new" not in rendered


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


def test_status_slash_command_prints_status(tmp_path):
    console = Console(record=True, width=200)

    next_session = _handle_slash_command(SlashCommand("status"), console, tmp_path, "s1")

    assert next_session == "s1"
    assert f"Project: {tmp_path}" in console.export_text()


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
    assert "usage input 10 · output 2 · total 12" in rendered


def test_print_usage_footer_shows_context_status(tmp_path):
    console = Console(record=True)
    session = DeepyJsonlSession.create(tmp_path, session_id="s1")
    session._touch_index(active_tokens=250)

    _print_usage_footer(
        console,
        RunSummary(
            output="ok",
            session_id="s1",
            complete=True,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=2, total_tokens=102),
        ),
        settings=Settings(context=ContextConfig(window_tokens=1_000, compact_trigger_ratio=0.8)),
        project_root=tmp_path,
    )

    rendered = console.export_text()
    assert "usage input 100 · output 2 · total 102" in rendered
    assert "context current input 100" in rendered
    assert "session 250 / 1,000 (25.0%)" in rendered
    assert "compact at 800" in rendered


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
    calls = 0

    def fake_prompt_for_input(session):
        nonlocal calls
        calls += 1
        raise EOFError

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(Settings(), project_root=tmp_path, console=console)

    rendered = console.export_text()
    assert result == 0
    assert calls == 2
    assert "Press Ctrl+D again to exit." in rendered


def test_run_interactive_resets_ctrl_d_exit_confirmation_after_input(tmp_path, monkeypatch):
    console = Console(record=True, width=160)
    events = iter([EOFError, "", EOFError, EOFError])
    calls = 0

    def fake_prompt_for_input(session):
        nonlocal calls
        calls += 1
        event = next(events)
        if event is EOFError:
            raise EOFError
        return event

    monkeypatch.setattr(terminal, "create_prompt_session", lambda **kwargs: object())
    monkeypatch.setattr(terminal, "prompt_for_input", fake_prompt_for_input)

    result = terminal.run_interactive(Settings(), project_root=tmp_path, console=console)

    rendered = console.export_text()
    assert result == 0
    assert calls == 4
    assert rendered.count("Press Ctrl+D again to exit.") == 2
