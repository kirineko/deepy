from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from deepy.background_tasks import (
    BackgroundTaskOutput,
    BackgroundTaskSnapshot,
)
from deepy.todos import TodoItem, todo_counts, todo_items_to_payload
from deepy.types.tool_payloads import AskUserOption, AskUserQuestion

from .constants import (
    IGNORED_DIRECTORY_ENTRIES,
    MAX_BASH_OUTPUT_CHARS,
    MAX_LINE_LENGTH,
)
from .shell_output import decode_shell_output
from .tool_dataclasses import ShellInvocation
from .shell_utils import (
    RuntimeEnvironment,
    build_disable_extglob_command,
    build_shell_init_command,
    detect_runtime_environment,
    rewrite_windows_null_redirect,
)


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


def _read_captured_output(stream, *, marker: str | None = None) -> tuple[str, str, bool]:
    from . import builtin

    max_capture_chars = builtin.MAX_BASH_CAPTURE_CHARS
    stream.flush()
    stream.seek(0)
    data = stream.read(max_capture_chars + 1)
    truncated = len(data) > max_capture_chars
    if truncated:
        data = data[:max_capture_chars]
    text, encoding = decode_shell_output(data, marker=marker)
    return text, encoding, truncated


def _build_shell_command(
    command: str,
    marker: str,
    *,
    shell_path: str | None = None,
    env: dict[str, str] | None = None,
    platform_name: str | None = None,
    os_name: str | None = None,
) -> ShellInvocation:
    resolved_shell = shell_path or _resolve_shell_path(env=env, os_name=os_name)
    runtime_environment = detect_runtime_environment(
        shell_path=resolved_shell,
        env=env,
        platform_name=platform_name,
        os_name=os_name,
    )
    process_env = _build_shell_process_env(runtime_environment, env)
    if runtime_environment.command_dialect == "powershell":
        return ShellInvocation(
            shell_path=resolved_shell,
            args=_build_powershell_args(command, marker),
            runtime_environment=runtime_environment,
            env=process_env,
        )
    if runtime_environment.command_dialect == "cmd":
        return ShellInvocation(
            shell_path=resolved_shell,
            args=_build_cmd_args(command, marker),
            runtime_environment=runtime_environment,
            env=process_env,
        )
    return ShellInvocation(
        shell_path=resolved_shell,
        args=_build_posix_shell_args(command, marker, resolved_shell),
        runtime_environment=runtime_environment,
        env=process_env,
    )


def _build_background_shell_command(
    command: str,
    *,
    shell_path: str | None = None,
    env: dict[str, str] | None = None,
    platform_name: str | None = None,
    os_name: str | None = None,
) -> ShellInvocation:
    resolved_shell = shell_path or _resolve_shell_path(env=env, os_name=os_name)
    runtime_environment = detect_runtime_environment(
        shell_path=resolved_shell,
        env=env,
        platform_name=platform_name,
        os_name=os_name,
    )
    process_env = _build_shell_process_env(runtime_environment, env)
    if runtime_environment.command_dialect == "powershell":
        return ShellInvocation(
            shell_path=resolved_shell,
            args=_build_background_powershell_args(command),
            runtime_environment=runtime_environment,
            env=process_env,
        )
    if runtime_environment.command_dialect == "cmd":
        return ShellInvocation(
            shell_path=resolved_shell,
            args=_build_background_cmd_args(command),
            runtime_environment=runtime_environment,
            env=process_env,
        )
    return ShellInvocation(
        shell_path=resolved_shell,
        args=_build_background_posix_shell_args(command, resolved_shell),
        runtime_environment=runtime_environment,
        env=process_env,
    )


def _build_shell_process_env(
    runtime_environment: RuntimeEnvironment,
    env: dict[str, str] | None = None,
) -> dict[str, str] | None:
    if runtime_environment.os_family != "windows":
        return dict(env) if env is not None else None
    process_env = dict(os.environ if env is None else env)
    process_env.setdefault("PYTHONUTF8", "1")
    process_env.setdefault("PYTHONIOENCODING", "utf-8")
    return process_env


def _build_posix_shell_args(command: str, marker: str, shell_path: str) -> list[str]:
    normalized_command = rewrite_windows_null_redirect(command)
    parts = [
        part
        for part in (
            build_shell_init_command(shell_path),
            build_disable_extglob_command(shell_path),
            normalized_command,
            "__deepy_exit=$?",
            f'printf \'\\n{marker}CWD=%s\\n{marker}EXIT=%s\\n\' "$PWD" "$__deepy_exit"',
            "exit $__deepy_exit",
        )
        if part
    ]
    return ["-c", "{ " + "; ".join(parts) + "; } < /dev/null"]


def _build_background_posix_shell_args(command: str, shell_path: str) -> list[str]:
    normalized_command = rewrite_windows_null_redirect(command)
    parts = [
        part
        for part in (
            build_shell_init_command(shell_path),
            build_disable_extglob_command(shell_path),
            normalized_command,
        )
        if part
    ]
    return ["-c", "{ " + "; ".join(parts) + "; } < /dev/null"]


def _build_powershell_args(command: str, marker: str) -> list[str]:
    script = "\n".join(
        [
            "$OutputEncoding = [System.Text.UTF8Encoding]::new($false)",
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)",
            "$global:LASTEXITCODE = $null",
            "try {",
            command,
            "    $__deepy_success = $?",
            "    $__deepy_last_exit = $global:LASTEXITCODE",
            "    if ($null -eq $__deepy_last_exit) {",
            "        if ($__deepy_success) { $__deepy_exit = 0 } else { $__deepy_exit = 1 }",
            "    } else {",
            "        $__deepy_exit = [int]$__deepy_last_exit",
            "    }",
            "} catch {",
            "    Write-Error $_",
            "    $__deepy_exit = 1",
            "}",
            "$__deepy_cwd = (Get-Location).ProviderPath",
            'Write-Output ""',
            f'Write-Output "{marker}CWD=$__deepy_cwd"',
            f'Write-Output "{marker}EXIT=$__deepy_exit"',
            "exit $__deepy_exit",
        ]
    )
    return ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script]


def _build_background_powershell_args(command: str) -> list[str]:
    script = "\n".join(
        [
            "$OutputEncoding = [System.Text.UTF8Encoding]::new($false)",
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)",
            command,
            "exit $LASTEXITCODE",
        ]
    )
    return ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script]


def _build_cmd_args(command: str, marker: str) -> list[str]:
    script = "\r\n".join(
        [
            command,
            'set "__deepy_exit=%ERRORLEVEL%"',
            "echo.",
            f"echo {marker}CWD=%CD%",
            f"echo {marker}EXIT=%__deepy_exit%",
            "exit /b %__deepy_exit%",
        ]
    )
    return ["/d", "/s", "/c", script]


def _build_background_cmd_args(command: str) -> list[str]:
    return ["/d", "/s", "/c", command]


def _resolve_shell_path(
    *,
    env: dict[str, str] | None = None,
    os_name: str | None = None,
) -> str:
    environment = env or os.environ
    resolved_os_name = os_name or os.name
    shell_path = environment.get("SHELL")
    if shell_path:
        return shell_path
    if resolved_os_name == "nt":
        if "PSModulePath" in environment:
            return (
                environment.get("POWERSHELL")
                or shutil.which("pwsh")
                or shutil.which("powershell")
                or "powershell.exe"
            )
        comspec = environment.get("COMSPEC") or environment.get("ComSpec")
        if comspec:
            return comspec
        return shutil.which("pwsh") or shutil.which("powershell") or "cmd.exe"
    return "/bin/zsh" if Path("/bin/zsh").exists() else "/bin/sh"


def _shell_metadata(
    cwd: Path,
    process_id: str | None,
    shell_invocation: ShellInvocation,
    *,
    exit_code: int | None = None,
    output_truncated: bool,
    capture_truncated: bool,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "cwd": str(cwd),
        "processId": process_id,
        "shellPath": shell_invocation.shell_path,
        "shellKind": shell_invocation.runtime_environment.shell_kind,
        "commandDialect": shell_invocation.runtime_environment.command_dialect,
        "pathStyle": shell_invocation.runtime_environment.path_style,
        "osFamily": shell_invocation.runtime_environment.os_family,
        "outputTruncated": output_truncated,
        "captureTruncated": capture_truncated,
    }
    if exit_code is not None:
        metadata["exitCode"] = exit_code
    return metadata


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _format_background_time(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))


def _background_task_payload(snapshot: BackgroundTaskSnapshot) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": snapshot.id,
        "command": snapshot.command,
        "cwd": snapshot.cwd,
        "status": snapshot.status,
        "startTime": _format_background_time(snapshot.start_time),
        "outputPath": str(snapshot.output_path),
        "stopRequested": snapshot.stop_requested,
    }
    if snapshot.pid is not None:
        payload["pid"] = snapshot.pid
    if snapshot.end_time is not None:
        payload["endTime"] = _format_background_time(snapshot.end_time)
    if snapshot.exit_code is not None:
        payload["exitCode"] = snapshot.exit_code
    if snapshot.error:
        payload["error"] = snapshot.error
    return payload


def _background_task_metadata(
    snapshot: BackgroundTaskSnapshot,
    *,
    shell_invocation: ShellInvocation,
) -> dict[str, object]:
    metadata = _background_task_payload(snapshot)
    metadata.update(
        {
            "kind": "background_task_launch",
            "taskId": snapshot.id,
            "task": _background_task_payload(snapshot),
            "runInBackground": True,
            "shellPath": shell_invocation.shell_path,
            "shellKind": shell_invocation.runtime_environment.shell_kind,
            "commandDialect": shell_invocation.runtime_environment.command_dialect,
            "pathStyle": shell_invocation.runtime_environment.path_style,
            "osFamily": shell_invocation.runtime_environment.os_family,
        }
    )
    return metadata


def _format_background_task_line(snapshot: BackgroundTaskSnapshot) -> str:
    pid = f" pid={snapshot.pid}" if snapshot.pid is not None else ""
    exit_code = f" exit={snapshot.exit_code}" if snapshot.exit_code is not None else ""
    stopped = " stop_requested" if snapshot.stop_requested else ""
    return f"{snapshot.id}\t{snapshot.status}{pid}{exit_code}{stopped}\t{snapshot.command}"


def _format_background_task_output(output: BackgroundTaskOutput) -> str:
    lines = [
        _format_background_task_line(output.task),
        f"Output: {output.output_preview_bytes}/{output.output_size_bytes} bytes",
    ]
    if output.more_available:
        lines.append("Showing the most recent output only; more output is available.")
    lines.append("")
    lines.append(output.output if output.output else "[No output captured yet.]")
    return "\n".join(lines).rstrip()


def _background_task_output_metadata(output: BackgroundTaskOutput) -> dict[str, object]:
    return {
        "kind": "background_task_output",
        "taskId": output.task.id,
        "task": _background_task_payload(output.task),
        "outputSizeBytes": output.output_size_bytes,
        "outputPreviewBytes": output.output_preview_bytes,
        "outputTruncated": output.output_truncated,
        "moreAvailable": output.more_available,
    }


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
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


def _string_key_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _parse_ask_user_questions(value: object) -> tuple[list[AskUserQuestion], str | None]:
    if not isinstance(value, list) or not value:
        return [], '"questions" must be a non-empty array.'

    questions: list[AskUserQuestion] = []
    for index, raw_item in enumerate(value):
        item = _string_key_dict(raw_item)
        if item is None:
            return [], f"Question at index {index} must be an object."

        question = _trimmed_string(item.get("question"))
        if not question:
            return [], f'Question at index {index} is missing a non-empty "question" string.'

        raw_options = item.get("options")
        if not isinstance(raw_options, list) or not raw_options:
            return [], f'Question at index {index} must include a non-empty "options" array.'

        options: list[AskUserOption] = []
        for option_index, raw_option in enumerate(raw_options):
            option = _string_key_dict(raw_option)
            if option is None:
                return [], f"Option {option_index} for question {index} must be an object."

            label = _trimmed_string(option.get("label"))
            if not label:
                return (
                    [],
                    f'Option {option_index} for question {index} is missing a non-empty "label" string.',
                )

            parsed_option: AskUserOption = {"label": label}
            description = _trimmed_string(option.get("description"))
            if description:
                parsed_option["description"] = description
            options.append(parsed_option)

        parsed_question: AskUserQuestion = {
            "question": question,
            "options": options,
        }
        multi_select = item.get("multiSelect")
        if isinstance(multi_select, bool):
            parsed_question["multiSelect"] = multi_select
        questions.append(parsed_question)

    return questions, None


def _build_question_summary(questions: list[AskUserQuestion]) -> str:
    lines = ["Waiting for user input."]
    for index, item in enumerate(questions):
        lines.append("")
        lines.append(f"{index + 1}. {item['question']}")
        lines.append(f"   Mode: {'multi-select' if item.get('multiSelect') else 'single-select'}")
        for option in item["options"]:
            lines.append(f"   - {option['label']}")
            if option.get("description"):
                lines.append(f"     {option['description']}")
        lines.append("   - Other")
    return "\n".join(lines)


def _todo_tool_metadata(
    todos: list[TodoItem],
    *,
    changed: bool,
    read_only: bool,
) -> dict[str, object]:
    return {
        "kind": "todo_list",
        "todos": todo_items_to_payload(todos),
        "counts": todo_counts(todos),
        "changed": changed,
        "readOnly": read_only,
    }


def _todo_tool_output(
    todos: list[TodoItem],
    *,
    changed: bool,
    read_only: bool,
) -> str:
    counts = todo_counts(todos)
    if read_only:
        prefix = "Current todo list"
    elif changed:
        prefix = "Todo list updated"
    else:
        prefix = "Todo list unchanged"
    return (
        f"{prefix}: {counts['completed']}/{counts['total']} completed. "
        "Continue the task without narrating this internal progress update unless it helps the user."
    )


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
