from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Literal

from .result import ToolResult

TestShellDecisionKind = Literal["allow", "approval_required", "deny"]

DEFAULT_TEST_SHELL_TIMEOUT_MS = 120_000
MAX_TEST_SHELL_OUTPUT_CHARS = 30_000
SHELL_COMPOSITION_RE = re.compile(r"(^|\s)(&&|\|\||;|\||>|<|&)(\s|$)")
COMMAND_SUBSTITUTION_RE = re.compile(r"`|\$\(|\n|<<")


@dataclass(frozen=True)
class TestShellDecision:
    __test__ = False

    decision: TestShellDecisionKind
    reason: str
    argv: tuple[str, ...] = ()
    category: str = "unsupported"
    matched_pattern: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


@dataclass(frozen=True)
class TestShellPolicy:
    __test__ = False

    allow_patterns: tuple[str, ...] = ()
    approval_required_patterns: tuple[str, ...] = ()


def classify_test_shell_command(
    command: str,
    *,
    policy: TestShellPolicy | None = None,
    platform_name: str = os.name,
) -> TestShellDecision:
    normalized = " ".join(command.strip().split())
    if not normalized:
        return TestShellDecision("deny", "Command is empty.")
    if SHELL_COMPOSITION_RE.search(command) or COMMAND_SUBSTITUTION_RE.search(command):
        return TestShellDecision(
            "deny",
            "Shell composition syntax is not allowed in test_shell.",
        )

    argv, error = split_test_shell_command(command, platform_name=platform_name)
    if error is not None:
        return TestShellDecision("deny", error)
    if not argv:
        return TestShellDecision("deny", "Command is empty.")

    deny = _global_deny_decision(argv)
    if deny is not None:
        return deny

    policy = policy or TestShellPolicy()
    for pattern in policy.approval_required_patterns:
        if _pattern_matches(normalized, pattern):
            return TestShellDecision(
                "approval_required",
                "Project policy requires approval for this command.",
                tuple(argv),
                "project_policy",
                pattern,
            )
    for pattern in policy.allow_patterns:
        if _pattern_matches(normalized, pattern):
            return TestShellDecision(
                "allow",
                "Allowed by project test_shell policy.",
                tuple(argv),
                "project_policy",
                pattern,
            )

    return _classify_known_command(argv)


def split_test_shell_command(
    command: str,
    *,
    platform_name: str = os.name,
) -> tuple[list[str], str | None]:
    try:
        argv = shlex.split(command, posix=platform_name != "win32")
        if platform_name == "win32":
            argv = [_strip_windows_quotes(arg) for arg in argv]
        return argv, None
    except ValueError as exc:
        return [], f"Malformed command: {exc}"


def run_test_shell_command(
    command: str,
    *,
    cwd: Path,
    policy: TestShellPolicy | None = None,
    platform_name: str = os.name,
    timeout_ms: int = DEFAULT_TEST_SHELL_TIMEOUT_MS,
    should_interrupt: Callable[[], bool] | None = None,
    approval_token: str | None = None,
    approved_commands: dict[str, str] | None = None,
    approved_by_audit: bool = False,
) -> str:
    name = "test_shell"
    decision = classify_test_shell_command(command, policy=policy, platform_name=platform_name)
    metadata = _decision_metadata(command, cwd, decision)
    if decision.decision == "deny":
        return ToolResult.error_result(name, decision.reason, metadata=metadata).to_json()
    if (
        decision.decision == "approval_required"
        and not approved_by_audit
        and not _approval_token_matches(command, approval_token, approved_commands)
    ):
        token = _approval_token_for(command, approved_commands)
        return ToolResult.error_result(
            name,
            "Command requires user approval before execution.",
            output=(
                f"Approval required for: {command}\n"
                f"Reason: {decision.reason}\n"
                f"approval_token: {token}"
            ),
            metadata={
                **metadata,
                "approvalToken": token,
                "approvalRequired": True,
            },
        ).to_json()

    timeout_seconds = max(1, min(int(timeout_ms or DEFAULT_TEST_SHELL_TIMEOUT_MS), 600_000)) / 1000
    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    interrupted = False
    try:
        process = subprocess.Popen(
            list(decision.argv),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
        interrupted = _wait_for_process(
            process,
            timeout=timeout_seconds,
            should_interrupt=should_interrupt,
        )
        if interrupted:
            _terminate_process(process)
        stdout, stderr = process.communicate(timeout=1)
    except FileNotFoundError:
        return ToolResult.error_result(
            name,
            f"Command executable not found: {decision.argv[0]}",
            metadata={**metadata, "error_code": "executable_not_found"},
        ).to_json()
    except Exception as exc:
        return ToolResult.error_result(
            name,
            f"Failed to execute command: {exc}",
            metadata={**metadata, "error_code": "execution_failed"},
        ).to_json()

    elapsed_ms = int((time.monotonic() - started) * 1000)
    returncode = int(process.returncode or 0)
    stdout_text, stdout_truncated = _truncate(stdout or "")
    stderr_text, stderr_truncated = _truncate(stderr or "")
    output = _format_output(command, returncode, stdout_text, stderr_text)
    output_text, output_truncated = _truncate(output)
    result_metadata = {
        **metadata,
        "approved": bool(approval_token or approved_by_audit),
        "approvedByAudit": approved_by_audit,
        "exitCode": returncode,
        "elapsedMs": elapsed_ms,
        "timeoutMs": int(timeout_seconds * 1000),
        "interrupted": interrupted,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdoutTruncated": stdout_truncated,
        "stderrTruncated": stderr_truncated,
        "outputTruncated": output_truncated,
    }
    if stdout_truncated or stderr_truncated or output_truncated:
        output_text = output_text.rstrip() + "\n... output truncated ..."
    if returncode == 0:
        return ToolResult.ok_result(name, output_text, metadata=result_metadata).to_json()
    return ToolResult.error_result(
        name,
        f"Command exited with code {returncode}.",
        output=output_text,
        metadata=result_metadata,
    ).to_json()


def _classify_known_command(argv: list[str]) -> TestShellDecision:
    exe = _basename(argv[0])
    lower = [arg.lower() for arg in argv]

    if exe == "uv":
        return _classify_uv(argv, lower)
    if exe in {"python", "python3", "pytest", "ruff", "ty", "mypy", "pyright", "pip", "pip3"}:
        return _classify_python_tools(exe, argv, lower)
    if exe in {"npm", "pnpm", "yarn", "bun"}:
        return _classify_node_tools(exe, argv, lower)
    if exe in {"mvn", "mvnw", "gradle", "gradlew"}:
        return _classify_jvm_tools(exe, argv, lower)
    if exe == "cargo":
        return _classify_cargo(argv, lower)
    if exe == "go":
        return _decision_for_subcommand(argv, {"test", "vet"}, "Go verification")
    if exe == "curl":
        return _classify_curl(argv, lower)
    if exe == "ping":
        return TestShellDecision("allow", "Network reachability diagnostic.", tuple(argv), "ping")
    if exe == "mysql":
        return _classify_mysql(argv)
    if exe == "docker":
        return _classify_docker(argv, lower)
    if exe in {"head", "tail"}:
        return TestShellDecision("allow", "Read-only file output diagnostic.", tuple(argv), exe)

    return TestShellDecision(
        "deny",
        "Command is not in test_shell's supported verification policy.",
        tuple(argv),
    )


def _classify_uv(argv: list[str], lower: list[str]) -> TestShellDecision:
    if len(argv) >= 3 and lower[1] == "pip" and lower[2] == "list":
        return TestShellDecision("allow", "Python environment inspection.", tuple(argv), "python")
    if len(argv) >= 3 and lower[1] == "pip" and lower[2] in {"install", "sync"}:
        return TestShellDecision(
            "approval_required",
            "Dependency installation can modify the local environment.",
            tuple(argv),
            "dependency_install",
        )
    if len(argv) >= 3 and lower[1] == "run":
        tool = _basename(argv[2]).lower()
        if tool in {"pytest", "ruff", "ty", "mypy", "pyright", "python", "python3"}:
            return TestShellDecision("allow", "Python verification command.", tuple(argv), "python")
        if tool == "pip" and len(argv) >= 5 and lower[3] == "list":
            return TestShellDecision("allow", "Python environment inspection.", tuple(argv), "python")
    if len(argv) >= 2 and lower[1] in {"sync", "pip"}:
        return TestShellDecision(
            "approval_required",
            "Dependency or environment operation requires approval.",
            tuple(argv),
            "dependency_install",
        )
    return TestShellDecision("deny", "Unsupported uv command for test_shell.", tuple(argv), "python")


def _classify_python_tools(exe: str, argv: list[str], lower: list[str]) -> TestShellDecision:
    if exe in {"pytest", "ruff", "ty", "mypy", "pyright"}:
        return TestShellDecision("allow", "Python verification command.", tuple(argv), "python")
    if exe in {"pip", "pip3"}:
        if len(argv) >= 2 and lower[1] == "list":
            return TestShellDecision("allow", "Python environment inspection.", tuple(argv), "python")
        if len(argv) >= 2 and lower[1] == "install":
            return TestShellDecision(
                "approval_required",
                "Dependency installation can modify the local environment.",
                tuple(argv),
                "dependency_install",
            )
    if len(argv) >= 3 and lower[1] == "-m":
        module = lower[2]
        if module in {"pytest", "ruff", "ty", "mypy", "pyright"}:
            return TestShellDecision("allow", "Python verification command.", tuple(argv), "python")
        if module == "pip" and len(argv) >= 4 and lower[3] == "list":
            return TestShellDecision("allow", "Python environment inspection.", tuple(argv), "python")
        if module == "pip" and len(argv) >= 4 and lower[3] == "install":
            return TestShellDecision(
                "approval_required",
                "Dependency installation can modify the local environment.",
                tuple(argv),
                "dependency_install",
            )
    return TestShellDecision("deny", "Unsupported Python command for test_shell.", tuple(argv), "python")


def _classify_node_tools(exe: str, argv: list[str], lower: list[str]) -> TestShellDecision:
    if any(arg == "publish" for arg in lower):
        return TestShellDecision("deny", "Package publishing is blocked.", tuple(argv), "publish")
    if len(argv) >= 2 and lower[1] in {"install", "add", "ci"}:
        return TestShellDecision(
            "approval_required",
            "Dependency installation can modify the local environment.",
            tuple(argv),
            "dependency_install",
        )
    allowed_scripts = {"test", "lint", "typecheck", "check", "build"}
    if len(argv) >= 2 and lower[1] in allowed_scripts:
        return TestShellDecision("allow", "Node/frontend verification command.", tuple(argv), "node")
    if len(argv) >= 3 and lower[1] == "run" and lower[2] in allowed_scripts:
        return TestShellDecision("allow", "Node/frontend verification command.", tuple(argv), "node")
    return TestShellDecision("deny", f"Unsupported {exe} command for test_shell.", tuple(argv), "node")


def _classify_jvm_tools(exe: str, argv: list[str], lower: list[str]) -> TestShellDecision:
    if any(arg == "deploy" for arg in lower):
        return TestShellDecision("deny", "Deploy/publish commands are blocked.", tuple(argv), "publish")
    if any(arg == "spring-boot:run" for arg in lower):
        return TestShellDecision(
            "approval_required",
            "Service startup can affect local runtime state.",
            tuple(argv),
            "service_startup",
        )
    allowed = {"test", "verify", "package", "check", "build"}
    if any(arg in allowed for arg in lower[1:]):
        return TestShellDecision("allow", "JVM verification command.", tuple(argv), "jvm")
    return TestShellDecision("deny", f"Unsupported {exe} command for test_shell.", tuple(argv), "jvm")


def _classify_cargo(argv: list[str], lower: list[str]) -> TestShellDecision:
    if len(argv) >= 2 and lower[1] in {"test", "check", "clippy"}:
        return TestShellDecision("allow", "Rust verification.", tuple(argv), "cargo")
    if len(argv) >= 2 and lower[1] == "run":
        return TestShellDecision(
            "approval_required",
            "cargo run executes local project code.",
            tuple(argv),
            "rust_run",
        )
    return TestShellDecision("deny", "Unsupported cargo command for test_shell.", tuple(argv), "cargo")


def _classify_curl(argv: list[str], lower: list[str]) -> TestShellDecision:
    mutating_methods = {"post", "put", "patch", "delete"}
    for index, arg in enumerate(lower):
        if arg in {"-x", "--request"} and index + 1 < len(lower):
            method = lower[index + 1]
            if method in mutating_methods:
                return TestShellDecision("deny", f"Mutating curl method {method.upper()} is blocked.", tuple(argv), "curl")
        if arg.startswith("-x") and len(arg) > 2 and arg[2:].lower() in mutating_methods:
            return TestShellDecision("deny", f"Mutating curl method {arg[2:].upper()} is blocked.", tuple(argv), "curl")
        if arg in {"-d", "--data", "--data-raw", "--form"}:
            return TestShellDecision("deny", "Mutating curl request body is blocked.", tuple(argv), "curl")
    return TestShellDecision("allow", "Read-only HTTP diagnostic.", tuple(argv), "curl")


def _classify_mysql(argv: list[str]) -> TestShellDecision:
    query = _mysql_query(argv)
    if not query:
        return TestShellDecision(
            "approval_required",
            "Interactive or connection-only mysql usage requires approval.",
            tuple(argv),
            "database",
        )
    first = query.strip().split(None, 1)[0].lower() if query.strip() else ""
    if first in {"select", "show", "describe", "desc", "explain"}:
        return TestShellDecision("allow", "Read-only mysql diagnostic.", tuple(argv), "database")
    return TestShellDecision("deny", "Mutating mysql statements are blocked.", tuple(argv), "database")


def _classify_docker(argv: list[str], lower: list[str]) -> TestShellDecision:
    if len(argv) >= 2 and lower[1] in {"ps", "logs"}:
        return TestShellDecision("allow", "Read-only Docker diagnostic.", tuple(argv), "docker")
    if len(argv) >= 3 and lower[1] == "system" and lower[2] == "prune":
        return TestShellDecision("deny", "docker system prune is blocked.", tuple(argv), "docker")
    if len(argv) >= 3 and lower[1] == "compose":
        subcommand = lower[2]
        if subcommand in {"ps", "logs", "config"}:
            return TestShellDecision("allow", "Read-only Docker Compose diagnostic.", tuple(argv), "docker")
        if subcommand in {"up", "build"}:
            return TestShellDecision(
                "approval_required",
                "Docker Compose startup/build can affect local runtime state.",
                tuple(argv),
                "docker",
            )
        if subcommand == "down" and "-v" in lower:
            return TestShellDecision("deny", "docker compose down -v is blocked.", tuple(argv), "docker")
    return TestShellDecision("deny", "Unsupported Docker command for test_shell.", tuple(argv), "docker")


def _decision_for_subcommand(
    argv: list[str],
    allowed: set[str],
    reason: str,
) -> TestShellDecision:
    if len(argv) >= 2 and argv[1].lower() in allowed:
        return TestShellDecision("allow", reason + ".", tuple(argv), _basename(argv[0]))
    return TestShellDecision(
        "deny",
        f"Unsupported {_basename(argv[0])} command for test_shell.",
        tuple(argv),
        _basename(argv[0]),
    )


def _global_deny_decision(argv: list[str]) -> TestShellDecision | None:
    exe = _basename(argv[0]).lower()
    lower = [arg.lower() for arg in argv]
    if exe in {"rm", "mv", "cp", "chmod", "chown", "touch", "mkdir"}:
        return TestShellDecision("deny", f"{exe} is blocked by test_shell policy.", tuple(argv), "destructive")
    if exe == "git" and len(argv) >= 2 and lower[1] in {
        "add",
        "checkout",
        "clean",
        "commit",
        "push",
        "reset",
    }:
        return TestShellDecision("deny", f"git {lower[1]} is blocked by test_shell policy.", tuple(argv), "git")
    if any(arg in {"publish", "deploy"} for arg in lower):
        return TestShellDecision("deny", "Publishing/deploy commands are blocked.", tuple(argv), "publish")
    return None


def _mysql_query(argv: list[str]) -> str:
    for index, arg in enumerate(argv):
        if arg in {"-e", "--execute"} and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("-e") and len(arg) > 2:
            return arg[2:]
        if arg.startswith("--execute="):
            return arg.split("=", 1)[1]
    return ""


def _wait_for_process(
    process: subprocess.Popen[str],
    *,
    timeout: float,
    should_interrupt: Callable[[], bool] | None,
) -> bool:
    deadline = time.monotonic() + timeout
    while process.poll() is None:
        if should_interrupt is not None and should_interrupt():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(0.05, remaining))
    return False


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=1)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _approval_token_for(command: str, approved_commands: dict[str, str] | None) -> str:
    import uuid

    if approved_commands is None:
        return ""
    for token, stored_command in approved_commands.items():
        if stored_command == command:
            return token
    token = uuid.uuid4().hex
    approved_commands[token] = command
    return token


def _approval_token_matches(
    command: str,
    approval_token: str | None,
    approved_commands: dict[str, str] | None,
) -> bool:
    if not approval_token or approved_commands is None:
        return False
    return approved_commands.get(approval_token) == command


def _decision_metadata(command: str, cwd: Path, decision: TestShellDecision) -> dict[str, object]:
    metadata: dict[str, object] = {
        "kind": "test_shell",
        "command": command,
        "cwd": str(cwd),
        "decision": decision.decision,
        "policyDecision": decision.decision,
        "policyReason": decision.reason,
        "category": decision.category,
        "argv": list(decision.argv),
    }
    if decision.matched_pattern:
        metadata["matchedPattern"] = decision.matched_pattern
    return metadata


def _format_output(command: str, exit_code: int, stdout: str, stderr: str) -> str:
    parts = [f"$ {command}", f"exit_code: {exit_code}"]
    if stdout:
        parts.extend(["", "stdout:", stdout.rstrip("\n")])
    if stderr:
        parts.extend(["", "stderr:", stderr.rstrip("\n")])
    return "\n".join(parts).rstrip()


def _truncate(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_TEST_SHELL_OUTPUT_CHARS:
        return value, False
    return value[:MAX_TEST_SHELL_OUTPUT_CHARS], True


def _pattern_matches(command: str, pattern: str) -> bool:
    pattern = pattern.strip()
    return bool(pattern) and fnmatch(command, pattern)


def _basename(value: str) -> str:
    value = value.replace("\\", "/").rstrip("/")
    base = value.rsplit("/", 1)[-1]
    if base.startswith("./"):
        base = base[2:]
    if base.endswith(".cmd") or base.endswith(".exe"):
        base = base.rsplit(".", 1)[0]
    return base


def _strip_windows_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
