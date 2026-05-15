from __future__ import annotations

import builtins
import shlex
import sys

import pytest

from deepy.sessions import DeepyJsonlSession, list_session_entries
from deepy.ui.local_command import (
    LocalCommandResult,
    build_synthetic_shell_transcript_items,
    parse_local_command,
    run_local_command,
    shell_tool_result_json,
)
from deepy.utils import json as json_utils


def test_parse_local_command_detects_bang_command():
    assert parse_local_command("!pwd").command == "pwd"  # type: ignore[union-attr]
    assert parse_local_command("  !pwd  ").command == "pwd"  # type: ignore[union-attr]
    assert parse_local_command("!") is not None
    assert parse_local_command("!").command == ""  # type: ignore[union-attr]
    assert parse_local_command("please run !pwd") is None


def test_run_local_command_success_captures_output(tmp_path):
    result = run_local_command(
        "printf ok",
        cwd=tmp_path,
        shell_path="/bin/sh",
        env={"SHELL": "/bin/sh", "PATH": "/bin:/usr/bin"},
    )

    assert result.ok
    assert result.exit_code == 0
    assert result.cwd == tmp_path
    assert result.tty_mode == "pty"
    assert "ok" in result.output


def test_run_local_command_non_zero_exit(tmp_path):
    result = run_local_command(
        "exit 7",
        cwd=tmp_path,
        shell_path="/bin/sh",
        env={"SHELL": "/bin/sh", "PATH": "/bin:/usr/bin"},
    )

    assert not result.ok
    assert result.exit_code == 7
    assert result.error == "Command exited with code 7."


def test_run_local_command_timeout_returns_partial_output(tmp_path):
    script = "import time; print('started', flush=True); time.sleep(2)"
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"

    result = run_local_command(
        command,
        cwd=tmp_path,
        timeout_ms=50,
        shell_path="/bin/sh",
        env={"SHELL": "/bin/sh", "PATH": "/bin:/usr/bin"},
    )

    assert not result.ok
    assert result.timed_out
    assert result.error == "Command timed out."
    assert "started" in result.output


def test_run_local_command_interruption_metadata(tmp_path):
    result = run_local_command(
        "sleep 2",
        cwd=tmp_path,
        timeout_ms=5_000,
        shell_path="/bin/sh",
        env={"SHELL": "/bin/sh", "PATH": "/bin:/usr/bin"},
        should_interrupt=lambda: True,
    )

    assert not result.ok
    assert result.interrupted
    assert result.error == "Command interrupted."


def test_run_local_command_applies_separate_display_and_context_limits(tmp_path):
    result = run_local_command(
        "printf 1234567890",
        cwd=tmp_path,
        display_limit=8,
        context_limit=5,
        shell_path="/bin/sh",
        env={"SHELL": "/bin/sh", "PATH": "/bin:/usr/bin"},
    )

    assert result.display_output_truncated
    assert result.context_output_truncated
    assert len(result.display_output) > len(result.context_output)


def test_run_local_command_does_not_persist_cd_between_commands(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    first = run_local_command(
        "cd subdir && pwd",
        cwd=tmp_path,
        shell_path="/bin/sh",
        env={"SHELL": "/bin/sh", "PATH": "/bin:/usr/bin"},
    )
    second = run_local_command(
        "pwd",
        cwd=tmp_path,
        shell_path="/bin/sh",
        env={"SHELL": "/bin/sh", "PATH": "/bin:/usr/bin"},
    )

    assert first.ok
    assert second.ok
    assert str(subdir) in first.output
    assert second.output.strip() == str(tmp_path)


def test_windows_runner_reports_missing_pywinpty(tmp_path, monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "winpty":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = run_local_command(
        "echo hi",
        cwd=tmp_path,
        shell_path="powershell.exe",
        platform_name="win32",
        os_name="nt",
        env={"PSModulePath": "modules"},
    )

    assert not result.ok
    assert result.tty_mode == "unavailable"
    assert "pywinpty" in (result.error or "")


def test_shell_tool_result_json_marks_local_command_metadata(tmp_path):
    result = LocalCommandResult(
        command="printf ok",
        output="ok",
        display_output="ok",
        context_output="ok",
        exit_code=0,
        cwd=tmp_path,
        shell_path="/bin/sh",
        shell_kind="unknown",
        command_dialect="posix",
        path_style="posix",
        os_family="macos",
        tty_mode="pty",
        duration_ms=1,
        timeout_ms=1000,
    )

    payload = json_utils.loads(shell_tool_result_json(result))

    assert payload["ok"] is True
    assert payload["name"] == "shell"
    assert payload["output"] == "ok"
    assert payload["metadata"]["localCommandMode"] is True
    assert payload["metadata"]["ttyMode"] == "pty"


def test_synthetic_shell_transcript_uses_agents_sdk_tool_item_shape(tmp_path):
    result = LocalCommandResult(
        command="printf ok",
        output="ok",
        display_output="ok",
        context_output="ok",
        exit_code=0,
        cwd=tmp_path,
        shell_path="/bin/sh",
        shell_kind="unknown",
        command_dialect="posix",
        path_style="posix",
        os_family="macos",
        tty_mode="pty",
        duration_ms=1,
        timeout_ms=1000,
    )

    items = build_synthetic_shell_transcript_items("!printf ok", result, call_id="call-local")

    assert items[1] == {
        "type": "function_call",
        "call_id": "call-local",
        "name": "shell",
        "arguments": '{"command":"printf ok"}',
    }
    assert items[2]["type"] == "function_call_output"
    assert items[2]["call_id"] == "call-local"


@pytest.mark.asyncio
async def test_synthetic_shell_transcript_round_trips_through_session(tmp_path):
    session = DeepyJsonlSession.create(tmp_path / "project", deepy_home=tmp_path / "home", session_id="s1")
    result = LocalCommandResult(
        command="printf ok",
        output="ok",
        display_output="ok",
        context_output="ok",
        exit_code=0,
        cwd=tmp_path / "project",
        shell_path="/bin/sh",
        shell_kind="unknown",
        command_dialect="posix",
        path_style="posix",
        os_family="macos",
        tty_mode="pty",
        duration_ms=1,
        timeout_ms=1000,
    )
    items = build_synthetic_shell_transcript_items("!printf ok", result, call_id="call-local")

    await session.add_items(items)

    assert await session.get_items() == items
    entries = list_session_entries(tmp_path / "project", deepy_home=tmp_path / "home")
    assert entries[0].active_tokens > 0
    assert entries[0].usage is None
