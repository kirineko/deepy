from __future__ import annotations

import shlex
import subprocess
import urllib.parse
import urllib.request
import uuid
from difflib import unified_diff
from dataclasses import dataclass, field
from pathlib import Path

from deepy.config import Settings

from .file_state import FileState
from .result import ToolResult


DEFAULT_LINE_LIMIT = 2_000
MAX_LINE_LENGTH = 2_000


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
            entries = _format_directory_entries(target)
            return ToolResult.ok_result(
                name,
                entries,
                metadata={
                    "path": str(target),
                    "kind": "directory",
                    "entryCount": len(list(target.iterdir())),
                },
            ).to_json()

        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = max(start_line, 1) - 1
        effective_limit = limit if limit and limit > 0 else DEFAULT_LINE_LIMIT
        selected = lines[start : start + effective_limit]
        formatted_lines = [_truncate_line(line) for line in selected]
        truncated = start + len(selected) < len(lines) or any(
            len(line) > MAX_LINE_LENGTH for line in selected
        )
        full_file_read = start == 0 and not truncated
        numbered = "\n".join(
            f"{idx + start + 1}: {line}" for idx, line in enumerate(formatted_lines)
        )
        if full_file_read:
            self.file_state.mark_read(target)
        return ToolResult.ok_result(
            name,
            numbered,
            metadata={
                "path": str(target),
                "kind": "file",
                "startLine": start + 1,
                "lineCount": len(selected),
                "lineLimit": effective_limit,
                "totalLines": len(lines),
                "truncated": truncated,
                "trackedForWrite": full_file_read,
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
        marker = f"__DEEPY_CWD_{uuid.uuid4().hex}__"
        script = (
            f"{command}\n"
            "__deepy_exit=$?\n"
            f"printf '\\n{marker}CWD=%s\\n{marker}EXIT=%s\\n' \"$PWD\" \"$__deepy_exit\"\n"
            "exit $__deepy_exit\n"
        )
        try:
            completed = subprocess.run(
                ["/bin/zsh", "-lc", script],
                cwd=self.cwd,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult.error_result(
                name,
                f"Command timed out after {timeout_ms}ms.",
                output=(exc.stdout or "") + (exc.stderr or ""),
                metadata={"cwd": str(self.cwd), "timeoutMs": timeout_ms},
            ).to_json()

        stdout, final_cwd, exit_code = _extract_bash_sentinel(completed.stdout or "", marker)
        if final_cwd is not None and final_cwd.is_dir():
            self.cwd = final_cwd
        returncode = exit_code if exit_code is not None else completed.returncode
        output = stdout + (completed.stderr or "")
        result = ToolResult.ok_result if returncode == 0 else ToolResult.error_result
        if returncode == 0:
            return result(
                name,
                output,
                metadata={"cwd": str(self.cwd), "exitCode": returncode},
            ).to_json()
        return result(
            name,
            f"Command exited with code {returncode}.",
            output=output,
            metadata={"cwd": str(self.cwd), "exitCode": returncode},
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
        api_url = self.settings.tools.web_search.api_url
        if not command and not api_url:
            return ToolResult.error_result(
                name,
                "WebSearch command or api_url is not configured.",
                metadata={"query": query},
            ).to_json()
        if command:
            return self._web_search_command(query, command)
        return self._web_search_api(query, api_url)

    def _web_search_command(self, query: str, command: str) -> str:
        name = "WebSearch"
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

    def _web_search_api(self, query: str, api_url: str) -> str:
        name = "WebSearch"
        separator = "&" if "?" in api_url else "?"
        url = f"{api_url}{separator}{urllib.parse.urlencode({'q': query})}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            return ToolResult.error_result(
                name,
                f"WebSearch API request failed: {exc}",
                metadata={"query": query, "apiUrl": api_url},
            ).to_json()
        return ToolResult.ok_result(
            name,
            body,
            metadata={"query": query, "apiUrl": api_url},
        ).to_json()

def _unified_diff(old: str, new: str, *, path: str) -> str:
    return "".join(
        unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _truncate_line(line: str) -> str:
    if len(line) <= MAX_LINE_LENGTH:
        return line
    return line[:MAX_LINE_LENGTH] + "... [truncated]"


def _format_directory_entries(path: Path) -> str:
    lines: list[str] = []
    for entry in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        suffix = "/" if entry.is_dir() else ""
        try:
            size = entry.stat().st_size
        except OSError:
            size = 0
        lines.append(f"{entry.name}{suffix}\t{size}")
    return "\n".join(lines)


def _extract_bash_sentinel(stdout: str, marker: str) -> tuple[str, Path | None, int | None]:
    start = stdout.rfind(f"\n{marker}CWD=")
    if start == -1:
        return stdout, None, None
    visible = stdout[:start]
    tail = stdout[start + 1 :].splitlines()
    cwd: Path | None = None
    exit_code: int | None = None
    for line in tail:
        if line.startswith(f"{marker}CWD="):
            cwd = Path(line.removeprefix(f"{marker}CWD=")).resolve()
        elif line.startswith(f"{marker}EXIT="):
            raw = line.removeprefix(f"{marker}EXIT=")
            if raw.isdigit():
                exit_code = int(raw)
    return visible, cwd, exit_code
