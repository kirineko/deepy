from __future__ import annotations

import shlex
import subprocess
from difflib import unified_diff
from dataclasses import dataclass, field
from pathlib import Path

from deepy.config import Settings

from .file_state import FileState
from .result import ToolResult


def _resolve_in_cwd(cwd: Path, path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve()


@dataclass
class ToolRuntime:
    cwd: Path
    settings: Settings
    file_state: FileState = field(default_factory=FileState)

    def read(self, path: str, start_line: int = 1, limit: int | None = None) -> str:
        name = "read"
        target = _resolve_in_cwd(self.cwd, path)
        if not target.exists():
            return ToolResult.error_result(name, f"File does not exist: {target}").to_json()
        if target.is_dir():
            return ToolResult.error_result(name, f"Path is a directory: {target}").to_json()

        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = max(start_line, 1) - 1
        selected = lines[start : start + limit if limit and limit > 0 else None]
        numbered = "\n".join(f"{idx + start + 1}: {line}" for idx, line in enumerate(selected))
        self.file_state.mark_read(target)
        return ToolResult.ok_result(
            name,
            numbered,
            metadata={
                "path": str(target),
                "startLine": start + 1,
                "lineCount": len(selected),
                "totalLines": len(lines),
            },
        ).to_json()

    def write(self, path: str, content: str) -> str:
        name = "write"
        target = _resolve_in_cwd(self.cwd, path)
        ok, error = self.file_state.check_writable(target, require_read=True)
        if not ok:
            return ToolResult.error_result(name, error or "File is not writable.").to_json()
        old_content = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.file_state.mark_written(target)
        return ToolResult.ok_result(
            name,
            f"Wrote {target}",
            metadata={
                "path": str(target),
                "diff": _unified_diff(old_content, content, path=str(target)),
            },
        ).to_json()

    def edit(self, path: str, old: str, new: str, replace_all: bool = False) -> str:
        name = "edit"
        target = _resolve_in_cwd(self.cwd, path)
        if not target.exists():
            return ToolResult.error_result(name, f"File does not exist: {target}").to_json()
        ok, error = self.file_state.check_writable(target, require_read=True)
        if not ok:
            return ToolResult.error_result(name, error or "File is not writable.").to_json()
        text = target.read_text(encoding="utf-8", errors="replace")
        if old not in text:
            return ToolResult.error_result(name, "Old text was not found in the file.").to_json()
        occurrences = text.count(old)
        if occurrences > 1 and not replace_all:
            return ToolResult.error_result(
                name,
                "Old text appears multiple times; set replace_all=true or provide a narrower snippet.",
                metadata={"occurrences": occurrences},
            ).to_json()
        updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
        target.write_text(updated, encoding="utf-8")
        self.file_state.mark_written(target)
        return ToolResult.ok_result(
            name,
            f"Edited {target}",
            metadata={
                "path": str(target),
                "occurrences": occurrences if replace_all else 1,
                "diff": _unified_diff(text, updated, path=str(target)),
            },
        ).to_json()

    def bash(self, command: str, timeout_ms: int = 120_000) -> str:
        name = "bash"
        timeout = max(timeout_ms, 1) / 1000
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.cwd,
                text=True,
                capture_output=True,
                timeout=timeout,
                executable="/bin/zsh",
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult.error_result(
                name,
                f"Command timed out after {timeout_ms}ms.",
                output=(exc.stdout or "") + (exc.stderr or ""),
                metadata={"cwd": str(self.cwd), "timeoutMs": timeout_ms},
            ).to_json()

        output = (completed.stdout or "") + (completed.stderr or "")
        self._update_cwd_from_cd(command)
        result = ToolResult.ok_result if completed.returncode == 0 else ToolResult.error_result
        if completed.returncode == 0:
            return result(
                name,
                output,
                metadata={"cwd": str(self.cwd), "exitCode": completed.returncode},
            ).to_json()
        return result(
            name,
            f"Command exited with code {completed.returncode}.",
            output=output,
            metadata={"cwd": str(self.cwd), "exitCode": completed.returncode},
        ).to_json()

    def ask_user_question(self, question: str) -> str:
        return ToolResult(
            ok=True,
            name="AskUserQuestion",
            output=question,
            metadata={"question": question},
            awaitUserResponse=True,
        ).to_json()

    def web_search(self, query: str) -> str:
        name = "WebSearch"
        command = self.settings.tools.web_search.command
        if not command:
            return ToolResult.error_result(
                name,
                "WebSearch command is not configured.",
                metadata={"query": query},
            ).to_json()
        completed = subprocess.run(
            f"{command} {shlex.quote(query)}",
            shell=True,
            cwd=self.cwd,
            text=True,
            capture_output=True,
            timeout=60,
            executable="/bin/zsh",
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0:
            return ToolResult.error_result(
                name,
                f"WebSearch command exited with code {completed.returncode}.",
                output=output,
                metadata={"query": query},
            ).to_json()
        return ToolResult.ok_result(name, output, metadata={"query": query}).to_json()

    def _update_cwd_from_cd(self, command: str) -> None:
        parts = shlex.split(command)
        if len(parts) >= 2 and parts[0] == "cd":
            target = _resolve_in_cwd(self.cwd, parts[1])
            if target.is_dir():
                self.cwd = target


def _unified_diff(old: str, new: str, *, path: str) -> str:
    return "".join(
        unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
