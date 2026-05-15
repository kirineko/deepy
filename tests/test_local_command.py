from __future__ import annotations

import builtins
import io
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


def _run_windows_test_command(command: str, tmp_path, **kwargs) -> LocalCommandResult:
    return run_local_command(
        command,
        cwd=tmp_path,
        shell_path="/bin/sh",
        platform_name="win32",
        os_name="nt",
        env={"PATH": "/bin:/usr/bin"},
        **kwargs,
    )


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


def test_windows_runner_uses_pipe_success_captures_output(tmp_path):
    result = _run_windows_test_command("printf ok", tmp_path)

    assert result.ok
    assert result.exit_code == 0
    assert result.tty_mode == "pipe"
    assert result.os_family == "windows"
    assert result.output == "ok"


def test_windows_runner_non_zero_exit(tmp_path):
    result = _run_windows_test_command("exit 7", tmp_path)

    assert not result.ok
    assert result.exit_code == 7
    assert result.tty_mode == "pipe"
    assert result.error == "Command exited with code 7."


def test_windows_runner_timeout_returns_partial_output(tmp_path):
    script = "import time; print('started', flush=True); time.sleep(2)"
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"

    result = _run_windows_test_command(command, tmp_path, timeout_ms=500)

    assert not result.ok
    assert result.timed_out
    assert result.tty_mode == "pipe"
    assert result.error == "Command timed out."
    assert "started" in result.output


def test_windows_runner_interruption_metadata(tmp_path):
    result = _run_windows_test_command("sleep 2", tmp_path, should_interrupt=lambda: True)

    assert not result.ok
    assert result.interrupted
    assert result.tty_mode == "pipe"
    assert result.error == "Command interrupted."


def test_windows_runner_does_not_require_pywinpty(tmp_path, monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "winpty":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = _run_windows_test_command("printf ok", tmp_path)

    assert result.ok
    assert result.tty_mode == "pipe"
    assert result.output == "ok"


def test_windows_runner_preserves_powershell_shell_args_without_shell_true(tmp_path, monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeProcess:
        stdout = io.BytesIO(b"ok\r\n")

        @staticmethod
        def poll():
            return 0

        @staticmethod
        def wait(timeout=None):
            return 0

    def fake_popen(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return FakeProcess()

    monkeypatch.setattr("deepy.ui.local_command.subprocess.Popen", fake_popen)

    result = run_local_command(
        "Write-Output ok",
        cwd=tmp_path,
        shell_path="powershell.exe",
        platform_name="win32",
        os_name="nt",
        env={"PSModulePath": "modules"},
    )

    assert result.ok
    assert result.output == "ok\n"
    assert calls[0]["args"] == [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Write-Output ok",
    ]
    assert calls[0]["kwargs"]["env"]["PYTHONUTF8"] == "1"  # type: ignore[index]
    assert calls[0]["kwargs"]["env"]["PYTHONIOENCODING"] == "utf-8"  # type: ignore[index]
    assert "shell" not in calls[0]["kwargs"]


def test_windows_runner_preserves_cmd_shell_args_without_shell_true(tmp_path, monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeProcess:
        stdout = io.BytesIO(b"ok\r\n")

        @staticmethod
        def poll():
            return 0

        @staticmethod
        def wait(timeout=None):
            return 0

    def fake_popen(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return FakeProcess()

    monkeypatch.setattr("deepy.ui.local_command.subprocess.Popen", fake_popen)

    result = run_local_command(
        "echo ok",
        cwd=tmp_path,
        shell_path="cmd.exe",
        platform_name="win32",
        os_name="nt",
        env={"ComSpec": "cmd.exe"},
    )

    assert result.ok
    assert result.output == "ok\n"
    assert calls[0]["args"] == ["cmd.exe", "/d", "/s", "/c", "echo ok"]
    assert "shell" not in calls[0]["kwargs"]


def test_windows_runner_normalizes_and_sanitizes_output(tmp_path):
    script = (
        "import sys; "
        "sys.stdout.buffer.write("
        "b'\\x1b[31m' + '中文'.encode('utf-8') + b'\\x1b[0m\\r\\nnext\\rline\\x01'"
        ")"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"

    result = _run_windows_test_command(command, tmp_path)

    assert result.ok
    assert result.output == "中文\nnext\nline"
    assert result.display_output == "中文\nnext\nline"
    assert result.context_output == "中文\nnext\nline"


def test_windows_runner_decodes_gbk_compatible_output(tmp_path):
    script = (
        "import sys; "
        "sys.stdout.buffer.write("
        "b'\\x1b[32m' + '状态: 正常\\r\\n'.encode('gb18030') + b'\\x1b[0m'"
        ")"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"

    result = _run_windows_test_command(command, tmp_path)

    assert result.ok
    assert result.output == "状态: 正常\n"
    assert result.display_output == "状态: 正常\n"
    assert result.context_output == "状态: 正常\n"
    assert "\ufffd" not in result.output


def test_windows_runner_decodes_utf16le_output(tmp_path):
    script = (
        "import sys; "
        "sys.stdout.buffer.write('WSL 状态: 正常\\r\\n'.encode('utf-16le'))"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"

    result = _run_windows_test_command(command, tmp_path)

    assert result.ok
    assert result.output == "WSL 状态: 正常\n"
    assert "\ufffd" not in result.output


def test_shell_tool_result_json_sanitizes_windows_output(tmp_path):
    result = LocalCommandResult(
        command="echo dirty",
        output="\x1b[31m中文\x1b[0m\r\nnext\x01",
        display_output="\x1b[31m中文\x1b[0m\r\nnext\x01",
        context_output="\x1b[31m中文\x1b[0m\r\nnext\x01",
        exit_code=0,
        cwd=tmp_path,
        shell_path="powershell.exe",
        shell_kind="powershell",
        command_dialect="powershell",
        path_style="windows",
        os_family="windows",
        tty_mode="pipe",
        duration_ms=1,
        timeout_ms=1000,
    )

    payload = json_utils.loads(shell_tool_result_json(result))

    assert payload["output"] == "中文\nnext"
    assert "\x1b" not in payload["output"]
    assert "\x01" not in payload["output"]


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


@pytest.mark.asyncio
async def test_windows_synthetic_shell_transcript_stores_sanitized_output(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    session = DeepyJsonlSession.create(project, deepy_home=tmp_path / "home", session_id="s1")
    script = (
        "import sys; "
        "sys.stdout.buffer.write("
        "b'\\x1b[31m' + '中文'.encode('utf-8') + b'\\x1b[0m\\r\\nnext\\x01'"
        ")"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"
    result = _run_windows_test_command(command, project)
    items = build_synthetic_shell_transcript_items(f"!{command}", result, call_id="call-local")

    await session.add_items(items)

    stored_items = await session.get_items()
    payload = json_utils.loads(stored_items[2]["output"])
    assert payload["output"] == "中文\nnext"
    assert payload["metadata"]["ttyMode"] == "pipe"
    assert "\x1b" not in payload["output"]


@pytest.mark.asyncio
async def test_windows_synthetic_shell_transcript_stores_decoded_output(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    session = DeepyJsonlSession.create(project, deepy_home=tmp_path / "home", session_id="s1")
    script = "import sys; sys.stdout.buffer.write('状态: 正常\\n'.encode('gb18030'))"
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"
    result = _run_windows_test_command(command, project)
    items = build_synthetic_shell_transcript_items(f"!{command}", result, call_id="call-local")

    await session.add_items(items)

    stored_items = await session.get_items()
    payload = json_utils.loads(stored_items[2]["output"])
    assert payload["output"] == "状态: 正常\n"
    assert "\ufffd" not in payload["output"]
