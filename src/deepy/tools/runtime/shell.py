from __future__ import annotations

import os
import subprocess
import tempfile
import time
import uuid

from deepy.background_tasks import BackgroundTaskLimitError

from ..result import ToolResult
from ..shell_command import (
    _background_task_metadata,
    _build_background_shell_command,
    _build_shell_command,
    _extract_bash_sentinel,
    _now_iso,
    _read_captured_output,
    _shell_metadata,
    _terminate_process,
    _truncate_output,
)
from ..test_shell import TestShellPolicy, run_test_shell_command
from .state import ToolRuntimeState


class ShellToolsMixin(ToolRuntimeState):
    def shell(
        self,
        command: str,
        timeout_ms: int = 120_000,
        *,
        run_in_background: bool = False,
    ) -> str:
        if run_in_background:
            return self._shell_background(command)

        name = "shell"
        timeout = max(timeout_ms, 1) / 1000
        marker = f"__DEEPY_CWD_{uuid.uuid4().hex}__"
        shell_invocation = _build_shell_command(command, marker)
        process: subprocess.Popen[bytes] | None = None
        process_id: str | None = None
        try:
            with (
                tempfile.TemporaryFile(mode="w+b") as stdout_file,
                tempfile.TemporaryFile(mode="w+b") as stderr_file,
            ):
                process = subprocess.Popen(
                    [shell_invocation.shell_path, *shell_invocation.args],
                    cwd=self.cwd,
                    env=shell_invocation.env,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    stdin=subprocess.DEVNULL,
                    start_new_session=os.name != "nt",
                )
                process_id = str(process.pid)
                self.running_processes[process_id] = {
                    "startTime": _now_iso(),
                    "command": command,
                }
                interrupted = self._wait_for_shell_process(process, timeout=timeout)
                if interrupted:
                    _terminate_process(process)
                    process.wait()
                    stdout, stdout_encoding, stdout_capture_truncated = _read_captured_output(
                        stdout_file, marker=marker
                    )
                    stderr, stderr_encoding, stderr_capture_truncated = _read_captured_output(
                        stderr_file
                    )
                    output, output_truncated = _truncate_output((stdout or "") + (stderr or ""))
                    metadata = _shell_metadata(
                        self.cwd,
                        process_id,
                        shell_invocation,
                        output_truncated=output_truncated,
                        capture_truncated=stdout_capture_truncated or stderr_capture_truncated,
                    )
                    metadata.update(
                        {
                            "timeoutMs": timeout_ms,
                            "interrupted": True,
                            "stdoutEncoding": stdout_encoding,
                            "stderrEncoding": stderr_encoding,
                        }
                    )
                    return ToolResult.error_result(
                        name,
                        "Command interrupted by user."
                        if self._should_interrupt()
                        else f"Command timed out after {timeout_ms}ms.",
                        output=output,
                        metadata=metadata,
                    ).to_json()
                stdout, stdout_encoding, stdout_capture_truncated = _read_captured_output(
                    stdout_file, marker=marker
                )
                stderr, stderr_encoding, stderr_capture_truncated = _read_captured_output(
                    stderr_file
                )
        finally:
            if process_id is not None:
                self.running_processes.pop(process_id, None)

        stdout, final_cwd, exit_code = _extract_bash_sentinel(stdout or "", marker)
        if final_cwd is not None and final_cwd.is_dir():
            self.cwd = final_cwd
        returncode = exit_code if exit_code is not None else process.returncode
        output, output_truncated = _truncate_output(stdout + (stderr or ""))
        metadata = _shell_metadata(
            self.cwd,
            process_id,
            shell_invocation,
            exit_code=returncode,
            output_truncated=output_truncated,
            capture_truncated=stdout_capture_truncated or stderr_capture_truncated,
        )
        metadata.update(
            {
                "stdoutEncoding": stdout_encoding,
                "stderrEncoding": stderr_encoding,
            }
        )
        if returncode == 0:
            return ToolResult.ok_result(
                name,
                output,
                metadata=metadata,
            ).to_json()
        return ToolResult.error_result(
            name,
            f"Command exited with code {returncode}.",
            output=output,
            metadata=metadata,
        ).to_json()
    def test_shell(
        self,
        command: str,
        timeout_ms: int = 120_000,
        *,
        approval_token: str | None = None,
        approved_by_audit: bool = False,
    ) -> str:
        return run_test_shell_command(
            command,
            cwd=self.cwd,
            policy=TestShellPolicy(
                allow_patterns=self.settings.tools.test_shell.allow_patterns,
                approval_required_patterns=(
                    self.settings.tools.test_shell.approval_required_patterns
                ),
            ),
            platform_name=self.platform_name,
            timeout_ms=timeout_ms,
            should_interrupt=self.should_interrupt,
            approval_token=approval_token,
            approved_commands=self.test_shell_approvals,
            approved_by_audit=approved_by_audit,
        )
    def _wait_for_shell_process(self, process: subprocess.Popen[bytes], *, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            if process.poll() is not None:
                return False
            if self._should_interrupt():
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(0.05, remaining))
    def _should_interrupt(self) -> bool:
        return bool(self.should_interrupt and self.should_interrupt())
    def _shell_background(self, command: str) -> str:
        name = "shell"
        shell_invocation = _build_background_shell_command(
            command,
            platform_name=self.platform_name,
        )
        try:
            snapshot = self.background_tasks.start(
                command=command,
                argv=[shell_invocation.shell_path, *shell_invocation.args],
                cwd=self.cwd,
                env=shell_invocation.env,
            )
        except BackgroundTaskLimitError as exc:
            return ToolResult.error_result(
                name,
                str(exc),
                metadata={
                    "kind": "background_task_launch",
                    "error_code": "background_task_limit",
                    "runningCount": self.background_tasks.running_count(),
                },
            ).to_json()
        except Exception as exc:
            return ToolResult.error_result(
                name,
                f"Failed to start background task: {exc}",
                metadata={
                    "kind": "background_task_launch",
                    "error_code": "background_task_launch_failed",
                },
            ).to_json()
        output = (
            f"Started background task {snapshot.id}.\n"
            f'Use task_output with task_id="{snapshot.id}" to inspect output, '
            "or task_stop to stop it."
        )
        metadata = _background_task_metadata(snapshot, shell_invocation=shell_invocation)
        return ToolResult.ok_result(name, output, metadata=metadata).to_json()
