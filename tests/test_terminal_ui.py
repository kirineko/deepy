from __future__ import annotations

from rich.console import Console

from deepy.config import Settings
from deepy.llm.events import DeepyStreamEvent
from deepy.sessions import SessionEntry
import deepy.ui.terminal as terminal
from deepy.ui import SlashCommand, parse_slash_command
from deepy.ui.clipboard import ClipboardImage
from deepy.ui.terminal import _collect_pending_question_response
from deepy.ui.terminal import _handle_slash_command
from deepy.ui.terminal import _print_stream_event


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
    attached_images = ["data:image/png;base64,x"]

    next_session = _handle_slash_command(
        SlashCommand("new"),
        console,
        tmp_path,
        "s1",
        loaded,
        attached_images=attached_images,
    )

    assert next_session is None
    assert loaded == []
    assert attached_images == []


def test_paste_image_slash_command_attaches_clipboard_image(tmp_path, monkeypatch):
    console = Console(record=True)
    attached_images: list[str] = []
    monkeypatch.setattr(
        terminal,
        "read_clipboard_image",
        lambda: ClipboardImage("data:image/png;base64,x", "image/png"),
    )

    next_session = _handle_slash_command(
        SlashCommand("paste-image"),
        console,
        tmp_path,
        "s1",
        attached_images=attached_images,
    )

    assert next_session == "s1"
    assert attached_images == ["data:image/png;base64,x"]
    assert "Attached clipboard image (1 total)." in console.export_text()


def test_clear_images_slash_command_clears_attachments(tmp_path):
    console = Console(record=True)
    attached_images = ["data:image/png;base64,x"]

    next_session = _handle_slash_command(
        SlashCommand("clear-images"),
        console,
        tmp_path,
        "s1",
        attached_images=attached_images,
    )

    assert next_session == "s1"
    assert attached_images == []
    assert "Cleared attached images." in console.export_text()


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
    assert "1. s1" in rendered
    assert "2. s2" in rendered
    assert "Resuming session s2" in rendered


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


def test_print_stream_event_shows_tool_call_and_output():
    console = Console(record=True)

    _print_stream_event(console, DeepyStreamEvent(kind="tool_call", name="read"))
    _print_stream_event(
        console,
        DeepyStreamEvent(
            kind="tool_output",
            text='{"ok":true,"name":"read","output":"","error":null,"metadata":{"path":"/tmp/a"}}',
        ),
    )

    rendered = console.export_text()
    assert "tool call: read" in rendered
    assert "tool output: read ok - /tmp/a" in rendered


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
