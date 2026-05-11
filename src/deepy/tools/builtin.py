from __future__ import annotations

import base64
import json
import math
import os
import re
import signal
import shlex
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from difflib import unified_diff
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from deepy.config import Settings

from .file_state import FileSnippet, FileState
from .result import ToolResult
from .shell_utils import build_disable_extglob_command
from .shell_utils import build_shell_init_command
from .shell_utils import rewrite_windows_null_redirect


DEFAULT_LINE_LIMIT = 2_000
MAX_LINE_LENGTH = 2_000
MAX_BASH_OUTPUT_CHARS = 30_000
MAX_BASH_CAPTURE_CHARS = 10 * 1024 * 1024
PDF_LARGE_PAGE_THRESHOLD = 10
PDF_MAX_PAGE_RANGE = 20
IGNORED_DIRECTORY_ENTRIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "wheels",
}


def _resolve_in_cwd(cwd: Path, path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve()


def _resolve_read_target(cwd: Path, path: str) -> tuple[Path | None, str | None]:
    candidate = Path(path).expanduser()
    target = _resolve_in_cwd(cwd, path)
    if target.exists() or candidate.is_absolute():
        return target, None
    if candidate.parts and candidate.parts[0] == "..":
        return None, "Relative read paths must stay within the current project."

    suffix = _normalize_relative_suffix(path)
    if not suffix:
        return target, None
    matches = _find_suffix_matches(cwd, suffix)
    if len(matches) > 1:
        shown = "\n".join(str(match) for match in matches[:3])
        more = f"\n...and {len(matches) - 3} more." if len(matches) > 3 else ""
        return (
            None,
            "File path is ambiguous and may refer to multiple files:\n" + shown + more,
        )
    if len(matches) == 1:
        return matches[0], None
    return target, None


def _snippet_metadata(snippet: FileSnippet) -> dict[str, object]:
    return {
        "id": snippet.id,
        "filePath": str(snippet.path),
        "file_path": str(snippet.path),
        "startLine": snippet.start_line,
        "endLine": snippet.end_line,
        "start_line": snippet.start_line,
        "end_line": snippet.end_line,
    }


def _edit_scope(text: str, snippet: FileSnippet | None) -> tuple[int, int]:
    if snippet is None:
        return 0, len(text)
    return _line_scope_offsets(text, snippet.start_line, snippet.end_line)


def _line_scope_offsets(text: str, start_line: int, end_line: int) -> tuple[int, int]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return 0, 0
    start_idx = min(max(start_line - 1, 0), len(lines))
    end_idx = min(max(end_line, start_idx), len(lines))
    start = sum(len(line) for line in lines[:start_idx])
    end = sum(len(line) for line in lines[:end_idx])
    return start, end


@dataclass
class ToolRuntime:
    cwd: Path
    settings: Settings
    file_state: FileState = field(default_factory=FileState)
    running_processes: dict[str, dict[str, str]] = field(default_factory=dict)

    def read(
        self,
        path: str,
        start_line: int = 1,
        limit: int | None = None,
        pages: str | None = None,
    ) -> str:
        name = "read"
        target, error = _resolve_read_target(self.cwd, path)
        if error is not None:
            return ToolResult.error_result(name, error).to_json()
        if target is None or not target.exists():
            return ToolResult.error_result(name, f"File does not exist: {path}").to_json()
        if target.is_dir():
            entries, visible_count, ignored_count = _format_directory_entries(target, self.cwd)
            return ToolResult.ok_result(
                name,
                entries,
                metadata={
                    "path": str(target),
                    "kind": "directory",
                    "entryCount": len(list(target.iterdir())),
                    "visibleEntryCount": visible_count,
                    "ignoredEntryCount": ignored_count,
                },
            ).to_json()

        if target.suffix.lower() == ".ipynb":
            output, error = _format_notebook(target)
            if error is not None:
                return ToolResult.error_result(name, error, metadata={"path": str(target)}).to_json()
            return ToolResult.ok_result(
                name,
                output,
                metadata={
                    "path": str(target),
                    "kind": "notebook",
                    "trackedForWrite": False,
                },
            ).to_json()

        if target.suffix.lower() == ".pdf":
            return _read_pdf(target, pages)

        mime = _image_mime_type(target.suffix.lower())
        if mime is not None:
            data = target.read_bytes()
            return ToolResult(
                ok=True,
                name=name,
                output="File loaded.",
                metadata={"path": str(target), "mime": mime, "bytes": len(data)},
                followUpMessages=[_build_image_follow_up_message(target, mime, data)],
            ).to_json()

        text = _read_text_preserving_newlines(target)
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
        snippet_metadata = None
        if not full_file_read and selected:
            snippet = self.file_state.create_snippet(
                target,
                start_line=start + 1,
                end_line=start + len(selected),
                text="\n".join(selected),
            )
            self.file_state.mark_read(target, full=False)
            snippet_metadata = _snippet_metadata(snippet)
        metadata = {
            "path": str(target),
            "kind": "file",
            "startLine": start + 1,
            "lineCount": len(selected),
            "lineLimit": effective_limit,
            "totalLines": len(lines),
            "truncated": truncated,
            "trackedForWrite": full_file_read,
        }
        if snippet_metadata is not None:
            metadata["snippet"] = snippet_metadata
        return ToolResult.ok_result(
            name,
            numbered,
            metadata=metadata,
        ).to_json()

    def write(self, path: str, content: object) -> str:
        name = "write"
        target = _resolve_in_cwd(self.cwd, path)
        ok, error = self.file_state.check_writable(target, require_read=True)
        if not ok:
            return ToolResult.error_result(name, error or "File is not writable.").to_json()
        text_content, repair_metadata, content_error = _coerce_write_content(target, content)
        if content_error is not None:
            return ToolResult.error_result(name, content_error).to_json()
        old_content = _read_text_preserving_newlines(target) if target.exists() else ""
        line_endings = _detect_line_endings(old_content or text_content)
        normalized_content = _normalize_line_endings(text_content, line_endings)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(normalized_content, encoding="utf-8")
        self.file_state.mark_written(target)
        diff = _unified_diff(old_content, normalized_content, path=str(target))
        return ToolResult.ok_result(
            name,
            f"Wrote {target}",
            metadata={
                "path": str(target),
                "line_endings": line_endings,
                **repair_metadata,
                "diff": diff,
                "diff_preview": diff,
            },
        ).to_json()

    def edit(
        self,
        path: str | None,
        old: str,
        new: str,
        replace_all: bool = False,
        snippet_id: str | None = None,
    ) -> str:
        name = "edit"
        if not old:
            return ToolResult.error_result(name, "old text must not be empty.").to_json()
        snippet = None
        if snippet_id:
            snippet = self.file_state.get_snippet(snippet_id)
            if snippet is None:
                return ToolResult.error_result(name, f"Unknown snippet_id: {snippet_id}").to_json()
            target = snippet.path
            if path:
                requested_target = _resolve_in_cwd(self.cwd, path)
                if requested_target != target:
                    return ToolResult.error_result(
                        name,
                        "snippet_id does not belong to the provided file path.",
                    ).to_json()
        else:
            if not path:
                return ToolResult.error_result(
                    name,
                    "path is required unless snippet_id is provided.",
                ).to_json()
            target = _resolve_in_cwd(self.cwd, path)
        if not target.exists():
            return ToolResult.error_result(name, f"File does not exist: {target}").to_json()
        ok, error = self.file_state.check_writable(
            target,
            require_read=True,
            allow_partial=snippet is not None,
        )
        if not ok:
            return ToolResult.error_result(name, error or "File is not writable.").to_json()
        text = _read_text_preserving_newlines(target)
        scope = _edit_scope(text, snippet)
        scoped_text = text[scope[0] : scope[1]]
        if old not in scoped_text:
            return ToolResult.error_result(name, "Old text was not found in the file.").to_json()
        occurrences = scoped_text.count(old)
        if occurrences > 1 and not replace_all:
            return ToolResult.error_result(
                name,
                "Old text appears multiple times; set replace_all=true or provide a narrower snippet.",
                metadata={"occurrences": occurrences},
            ).to_json()
        line_endings = _detect_line_endings(text)
        normalized_new = _normalize_line_endings(new, line_endings)
        updated_scope = (
            scoped_text.replace(old, normalized_new)
            if replace_all
            else scoped_text.replace(old, normalized_new, 1)
        )
        updated = text[: scope[0]] + updated_scope + text[scope[1] :]
        target.write_text(updated, encoding="utf-8")
        self.file_state.mark_written(target)
        diff = _unified_diff(text, updated, path=str(target))
        metadata = {
            "path": str(target),
            "file_path": str(target),
            "occurrences": occurrences if replace_all else 1,
            "line_endings": line_endings,
            "read_scope_type": "snippet" if snippet is not None else "full",
            "diff": diff,
            "diff_preview": diff,
        }
        if snippet is not None:
            metadata["scope"] = _snippet_metadata(snippet)
        return ToolResult.ok_result(name, f"Edited {target}", metadata=metadata).to_json()

    def bash(self, command: str, timeout_ms: int = 120_000) -> str:
        name = "bash"
        timeout = max(timeout_ms, 1) / 1000
        marker = f"__DEEPY_CWD_{uuid.uuid4().hex}__"
        shell_path, shell_args = _build_shell_command(command, marker)
        process: subprocess.Popen[str] | None = None
        process_id: str | None = None
        try:
            with (
                tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stdout_file,
                tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stderr_file,
            ):
                process = subprocess.Popen(
                    [shell_path, *shell_args],
                    cwd=self.cwd,
                    text=True,
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
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    _terminate_process(process)
                    process.wait()
                    stdout, stdout_capture_truncated = _read_captured_output(stdout_file)
                    stderr, stderr_capture_truncated = _read_captured_output(stderr_file)
                    output, output_truncated = _truncate_output((stdout or "") + (stderr or ""))
                    return ToolResult.error_result(
                        name,
                        f"Command timed out after {timeout_ms}ms.",
                        output=output,
                        metadata={
                            "cwd": str(self.cwd),
                            "timeoutMs": timeout_ms,
                            "processId": process_id,
                            "shellPath": shell_path,
                            "interrupted": True,
                            "outputTruncated": output_truncated,
                            "captureTruncated": stdout_capture_truncated
                            or stderr_capture_truncated,
                        },
                    ).to_json()
                stdout, stdout_capture_truncated = _read_captured_output(stdout_file)
                stderr, stderr_capture_truncated = _read_captured_output(stderr_file)
        finally:
            if process_id is not None:
                self.running_processes.pop(process_id, None)

        stdout, final_cwd, exit_code = _extract_bash_sentinel(stdout or "", marker)
        if final_cwd is not None and final_cwd.is_dir():
            self.cwd = final_cwd
        returncode = exit_code if exit_code is not None else process.returncode
        output, output_truncated = _truncate_output(stdout + (stderr or ""))
        result = ToolResult.ok_result if returncode == 0 else ToolResult.error_result
        if returncode == 0:
            return result(
                name,
                output,
                metadata={
                    "cwd": str(self.cwd),
                    "exitCode": returncode,
                    "processId": process_id,
                    "shellPath": shell_path,
                    "outputTruncated": output_truncated,
                    "captureTruncated": stdout_capture_truncated or stderr_capture_truncated,
                },
            ).to_json()
        return result(
            name,
            f"Command exited with code {returncode}.",
            output=output,
            metadata={
                "cwd": str(self.cwd),
                "exitCode": returncode,
                "processId": process_id,
                "shellPath": shell_path,
                "outputTruncated": output_truncated,
                "captureTruncated": stdout_capture_truncated or stderr_capture_truncated,
            },
        ).to_json()

    def ask_user_question(self, questions: object) -> str:
        parsed_questions, error = _parse_ask_user_questions(questions)
        if error is not None:
            return ToolResult.error_result("AskUserQuestion", error).to_json()
        return ToolResult(
            ok=True,
            name="AskUserQuestion",
            output=_build_question_summary(parsed_questions),
            metadata={"kind": "ask_user_question", "questions": parsed_questions},
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


def _read_text_preserving_newlines(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def _coerce_write_content(path: Path, content: object) -> tuple[str, dict[str, object], str | None]:
    if isinstance(content, str):
        return content, {}, None
    if path.suffix.lower() == ".json" and content is not None and not isinstance(content, bytes):
        try:
            return (
                json.dumps(content, ensure_ascii=False, indent=2),
                {"input_repaired": True, "repair_kind": "json-stringify-content"},
                None,
            )
        except TypeError as exc:
            return "", {}, f"JSON content is not serializable: {exc}"
    return "", {}, "content must be a string."


def _format_notebook(path: Path) -> tuple[str, str | None]:
    raw = _read_text_preserving_newlines(path)
    if not raw:
        return "WARNING: File is empty.", None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return "", f"Failed to parse notebook JSON: {exc}"
    if not isinstance(parsed, dict):
        return "WARNING: Notebook has no cells.", None

    cells = parsed.get("cells")
    lines: list[str] = []
    if isinstance(cells, list):
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict):
                continue
            cell_type = cell.get("cell_type") if isinstance(cell.get("cell_type"), str) else "unknown"
            lines.append(f"# Cell {index + 1} ({cell_type})")
            lines.extend(_normalize_notebook_field(cell.get("source")))

            outputs = cell.get("outputs")
            if not isinstance(outputs, list):
                continue
            for output_index, output in enumerate(outputs):
                if not isinstance(output, dict):
                    continue
                output_type = (
                    output.get("output_type")
                    if isinstance(output.get("output_type"), str)
                    else "output"
                )
                lines.append(f"# Output {output_index + 1} ({output_type})")
                lines.extend(_format_notebook_output(output))

    if not lines:
        return "WARNING: Notebook has no cells.", None
    return "\n".join(f"{idx + 1}: {line}" for idx, line in enumerate(lines)), None


def _normalize_notebook_field(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).removesuffix("\n").removesuffix("\r") for item in value]
    if isinstance(value, str):
        return value.splitlines()
    return []


def _format_notebook_output(output: dict[str, object]) -> list[str]:
    lines = _normalize_notebook_field(output.get("text"))
    data = output.get("data")
    if isinstance(data, dict):
        lines.extend(_normalize_notebook_field(data.get("text/plain")))
        image_png = data.get("image/png")
        if isinstance(image_png, str):
            lines.append(f"[image/png {len(image_png)} chars]")
        image_jpeg = data.get("image/jpeg")
        if isinstance(image_jpeg, str):
            lines.append(f"[image/jpeg {len(image_jpeg)} chars]")
    traceback = output.get("traceback")
    if isinstance(traceback, list):
        lines.extend(str(item).removesuffix("\n").removesuffix("\r") for item in traceback)
    return lines or ["[output omitted]"]


@dataclass(frozen=True)
class PageRange:
    start: int
    end: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    def label(self) -> str:
        return f"{self.start}-{self.end}"


def _read_pdf(path: Path, pages: str | None) -> str:
    data = path.read_bytes()
    page_count = _count_pdf_pages(data)
    page_range, range_error = _parse_page_range(pages)
    if range_error is not None:
        return ToolResult.error_result("read", range_error, metadata={"path": str(path)}).to_json()

    if page_range is None and page_count is not None and page_count > PDF_LARGE_PAGE_THRESHOLD:
        return ToolResult.error_result(
            "read",
            f'PDF has {page_count} pages; provide "pages" to read a range.',
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()
    if page_range is not None and page_range.count > PDF_MAX_PAGE_RANGE:
        return ToolResult.error_result(
            "read",
            f"PDF page range exceeds {PDF_MAX_PAGE_RANGE} pages.",
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()
    if page_range is not None and page_count is not None and page_range.end > page_count:
        return ToolResult.error_result(
            "read",
            f"PDF page range exceeds total page count ({page_count}).",
            metadata={"path": str(path), "pageCount": page_count},
        ).to_json()

    encoded = base64.b64encode(data).decode("ascii")
    return ToolResult.ok_result(
        "read",
        f"data:application/pdf;base64,{encoded}",
        metadata={
            "path": str(path),
            "mime": "application/pdf",
            "encoding": "base64",
            "bytes": len(data),
            "pageCount": page_count,
            "pages": page_range.label() if page_range is not None else None,
        },
    ).to_json()


def _count_pdf_pages(data: bytes) -> int | None:
    try:
        text = data.decode("latin1", errors="ignore")
    except Exception:
        return None
    return len(re.findall(r"/Type\s*/Page\b(?!s)", text))


def _parse_page_range(value: str | None) -> tuple[PageRange | None, str | None]:
    if value is None or not value.strip():
        return None, None
    trimmed = value.strip()
    if "," in trimmed:
        return None, 'pages must be a single range like "1-5" or "3".'
    parts = [part.strip() for part in trimmed.split("-")]
    if len(parts) == 1:
        start, error = _parse_positive_int(parts[0], "pages")
        return (PageRange(start, start), None) if error is None else (None, error)
    if len(parts) == 2:
        start, start_error = _parse_positive_int(parts[0], "pages")
        if start_error is not None:
            return None, start_error
        end, end_error = _parse_positive_int(parts[1], "pages")
        if end_error is not None:
            return None, end_error
        if end < start:
            return None, "pages range end must be >= start."
        return PageRange(start, end), None
    return None, 'pages must be a single range like "1-5" or "3".'


def _parse_positive_int(value: str, label: str) -> tuple[int, str | None]:
    try:
        numeric = float(value)
    except ValueError:
        return 0, f"{label} must be a number."
    if not math.isfinite(numeric):
        return 0, f"{label} must be a number."
    integer = int(numeric)
    if integer < 1:
        return 0, f"{label} must be >= 1."
    return integer, None


IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".avif": "image/avif",
}


def _image_mime_type(suffix: str) -> str | None:
    return IMAGE_MIME_TYPES.get(suffix)


def _build_image_follow_up_message(path: Path, mime: str, data: bytes) -> dict[str, object]:
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "role": "system",
        "content": (
            f"The read tool has loaded `{path.name}`. "
            "Use the attached image content to answer the original request."
        ),
        "contentParams": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            }
        ],
    }


def _detect_line_endings(text: str) -> str:
    return "CRLF" if "\r\n" in text else "LF"


def _normalize_line_endings(text: str, line_endings: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n") if line_endings == "CRLF" else normalized


def _truncate_line(line: str) -> str:
    if len(line) <= MAX_LINE_LENGTH:
        return line
    return line[:MAX_LINE_LENGTH] + "... [truncated]"


def _truncate_output(output: str, max_chars: int = MAX_BASH_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(output) <= max_chars:
        return output, False
    omitted = len(output) - max_chars
    return output[:max_chars] + f"\n... [truncated {omitted} chars]", True


def _read_captured_output(stream) -> tuple[str, bool]:
    stream.flush()
    stream.seek(0)
    text = stream.read(MAX_BASH_CAPTURE_CHARS + 1)
    if len(text) <= MAX_BASH_CAPTURE_CHARS:
        return text, False
    return text[:MAX_BASH_CAPTURE_CHARS], True


def _build_shell_command(command: str, marker: str) -> tuple[str, list[str]]:
    shell_path = _resolve_shell_path()
    normalized_command = rewrite_windows_null_redirect(command)
    parts = [
        part
        for part in (
            build_shell_init_command(shell_path),
            build_disable_extglob_command(shell_path),
            normalized_command,
            "__deepy_exit=$?",
            f"printf '\\n{marker}CWD=%s\\n{marker}EXIT=%s\\n' \"$PWD\" \"$__deepy_exit\"",
            "exit $__deepy_exit",
        )
        if part
    ]
    return shell_path, ["-c", "{ " + "; ".join(parts) + "; } < /dev/null"]


def _resolve_shell_path() -> str:
    shell_path = os.environ.get("SHELL")
    if shell_path:
        return shell_path
    return "/bin/zsh" if Path("/bin/zsh").exists() else "/bin/sh"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except OSError:
        return


def _format_directory_entries(path: Path, project_root: Path) -> tuple[str, int, int]:
    lines: list[str] = []
    ignored_count = 0
    gitignore = _load_gitignore_matcher(project_root)
    for entry in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if _is_ignored_entry(entry, project_root, gitignore):
            ignored_count += 1
            continue
        suffix = "/" if entry.is_dir() else ""
        try:
            size = entry.stat().st_size
        except OSError:
            size = 0
        lines.append(f"{entry.name}{suffix}\t{size}")
    return "\n".join(lines), len(lines), ignored_count


def _normalize_relative_suffix(path: str) -> str:
    suffix = path.replace("\\", "/").strip("/")
    parts = [part for part in suffix.split("/") if part and part != "."]
    return "/".join(parts)


def _find_suffix_matches(root: Path, suffix: str) -> list[Path]:
    matches: list[Path] = []
    gitignore = _load_gitignore_matcher(root)
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not _is_ignored_entry(Path(current) / dirname, root, gitignore)
        ]
        current_path = Path(current)
        for filename in filenames:
            full_path = current_path / filename
            if _is_ignored_entry(full_path, root, gitignore):
                continue
            try:
                relative = full_path.relative_to(root).as_posix()
            except ValueError:
                continue
            if relative.endswith(suffix):
                matches.append(full_path.resolve())
    return matches


def _is_ignored_entry(
    path: Path,
    project_root: Path,
    gitignore: "GitignoreMatcher",
) -> bool:
    if path.name in IGNORED_DIRECTORY_ENTRIES:
        return True
    try:
        relative = path.relative_to(project_root).as_posix()
    except ValueError:
        return False
    return gitignore.ignores(relative, path.is_dir())


@dataclass(frozen=True)
class GitignorePattern:
    pattern: str
    negated: bool = False


@dataclass(frozen=True)
class GitignoreMatcher:
    patterns: tuple[GitignorePattern, ...]

    def ignores(self, relative_path: str, is_dir: bool) -> bool:
        normalized = relative_path.strip("/")
        if not normalized:
            return False
        ignored = False
        for item in self.patterns:
            if _gitignore_pattern_matches(item.pattern, normalized, is_dir):
                ignored = not item.negated
        return ignored


def _load_gitignore_matcher(project_root: Path) -> GitignoreMatcher:
    gitignore = project_root / ".gitignore"
    if not gitignore.is_file():
        return GitignoreMatcher(())
    patterns: list[GitignorePattern] = []
    for raw_line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
        if line:
            patterns.append(GitignorePattern(line.replace("\\", "/"), negated))
    return GitignoreMatcher(tuple(patterns))


def _gitignore_pattern_matches(pattern: str, relative_path: str, is_dir: bool) -> bool:
    directory_only = pattern.endswith("/")
    normalized_pattern = pattern.strip("/")
    if not normalized_pattern:
        return False
    if directory_only and not is_dir:
        return relative_path.startswith(normalized_pattern + "/")
    if "/" in normalized_pattern:
        return fnmatch(relative_path, normalized_pattern) or relative_path.startswith(
            normalized_pattern + "/"
        )
    parts = relative_path.split("/")
    return any(fnmatch(part, normalized_pattern) for part in parts)


def _parse_ask_user_questions(value: object) -> tuple[list[dict[str, object]], str | None]:
    if not isinstance(value, list) or not value:
        return [], '"questions" must be a non-empty array.'

    questions: list[dict[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            return [], f"Question at index {index} must be an object."

        question = _trimmed_string(item.get("question"))
        if not question:
            return [], f'Question at index {index} is missing a non-empty "question" string.'

        raw_options = item.get("options")
        if not isinstance(raw_options, list) or not raw_options:
            return [], f'Question at index {index} must include a non-empty "options" array.'

        options: list[dict[str, str]] = []
        for option_index, option in enumerate(raw_options):
            if not isinstance(option, dict):
                return [], f"Option {option_index} for question {index} must be an object."

            label = _trimmed_string(option.get("label"))
            if not label:
                return (
                    [],
                    f'Option {option_index} for question {index} is missing a non-empty "label" string.',
                )

            parsed_option = {"label": label}
            description = _trimmed_string(option.get("description"))
            if description:
                parsed_option["description"] = description
            options.append(parsed_option)

        parsed_question: dict[str, object] = {
            "question": question,
            "options": options,
        }
        multi_select = item.get("multiSelect")
        if isinstance(multi_select, bool):
            parsed_question["multiSelect"] = multi_select
        questions.append(parsed_question)

    return questions, None


def _build_question_summary(questions: list[dict[str, object]]) -> str:
    lines = ["Waiting for user input."]
    for index, item in enumerate(questions):
        lines.append("")
        lines.append(f"{index + 1}. {item['question']}")
        lines.append(f"   Mode: {'multi-select' if item.get('multiSelect') else 'single-select'}")
        for option in item["options"]:
            if not isinstance(option, dict):
                continue
            lines.append(f"   - {option['label']}")
            if option.get("description"):
                lines.append(f"     {option['description']}")
        lines.append("   - Other")
    return "\n".join(lines)


def _trimmed_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


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
