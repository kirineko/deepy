from __future__ import annotations

import sys

from deepy.tools.test_shell import (
    TestShellPolicy,
    classify_test_shell_command,
    run_test_shell_command,
    split_test_shell_command,
)
from deepy.utils import json as json_utils


def test_test_shell_allows_common_verification_families():
    allowed = [
        "uv run pytest",
        "python -m pytest tests",
        "pip list",
        "npm run test",
        "pnpm run lint",
        "yarn build",
        "bun test",
        "mvn test",
        "./mvnw verify",
        "gradle test",
        "./gradlew build",
        "mvn package",
        "cargo clippy",
        "go test ./...",
        "curl https://example.com",
        "ping 127.0.0.1",
        "mysql -e 'SELECT 1'",
        "docker ps",
        "docker compose logs",
        "head README.md",
        "tail README.md",
    ]

    for command in allowed:
        assert classify_test_shell_command(command).decision == "allow", command


def test_test_shell_approval_required_and_denied_commands():
    approval = [
        "pip install pytest",
        "npm install",
        "mvn spring-boot:run",
        "docker compose up",
    ]
    denied = [
        "rm -rf build",
        "git push",
        "npm publish",
        "docker system prune",
        "docker compose down -v",
        "curl -X POST https://example.com",
        "mysql -e 'DROP DATABASE app'",
        "pytest | cat",
    ]

    for command in approval:
        assert classify_test_shell_command(command).decision == "approval_required", command
    for command in denied:
        assert classify_test_shell_command(command).decision == "deny", command


def test_test_shell_executes_allowed_command_and_captures_output(tmp_path):
    command = f"{sys.executable} -c 'print(\"ok\")'"
    result = json_utils.loads(
        run_test_shell_command(
            command,
            cwd=tmp_path,
            policy=TestShellPolicy(allow_patterns=(f"{sys.executable} -c *",)),
        )
    )

    assert result["ok"] is True
    assert result["name"] == "test_shell"
    assert result["metadata"]["exitCode"] == 0
    assert result["metadata"]["cwd"] == str(tmp_path)
    assert "stdout:" in result["output"]
    assert "ok" in result["metadata"]["stdout"]


def test_test_shell_requires_token_for_approval_retry(tmp_path):
    approvals: dict[str, str] = {}
    command = "npm install"
    first = json_utils.loads(
        run_test_shell_command(command, cwd=tmp_path, approved_commands=approvals)
    )

    assert first["ok"] is False
    assert first["metadata"]["decision"] == "approval_required"
    token = first["metadata"]["approvalToken"]
    assert approvals[token] == command

    second = json_utils.loads(
        run_test_shell_command(
            command,
            cwd=tmp_path,
            approved_commands=approvals,
            approval_token="wrong",
        )
    )
    assert second["metadata"]["approvalRequired"] is True


def test_test_shell_timeout_and_output_truncation(tmp_path):
    timeout_command = f"{sys.executable} -c 'import time; time.sleep(1)'"
    timeout_result = json_utils.loads(
        run_test_shell_command(
            timeout_command,
            cwd=tmp_path,
            policy=TestShellPolicy(allow_patterns=(f"{sys.executable} -c *",)),
            timeout_ms=50,
        )
    )
    assert timeout_result["ok"] is False
    assert timeout_result["metadata"]["interrupted"] is True

    output_command = f"{sys.executable} -c 'print(\"x\" * 40000)'"
    output_result = json_utils.loads(
        run_test_shell_command(
            output_command,
            cwd=tmp_path,
            policy=TestShellPolicy(allow_patterns=(f"{sys.executable} -c *",)),
        )
    )
    assert output_result["metadata"]["stdoutTruncated"] is True
    assert "output truncated" in output_result["output"]


def test_test_shell_cross_platform_command_parsing():
    argv, error = split_test_shell_command(r'python -m pytest "tests\unit test"', platform_name="win32")

    assert error is None
    assert argv == ["python", "-m", "pytest", r"tests\unit test"]

    _, malformed = split_test_shell_command("'unterminated", platform_name="posix")
    assert malformed is not None
