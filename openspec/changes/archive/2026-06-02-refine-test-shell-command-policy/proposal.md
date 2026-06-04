# Refine test_shell command policy

## Why

Tester subagents use `test_shell` for verification. Some useful local-code
execution commands, especially `python script.py`, are currently classified as
unsupported hard denials. That prevents audit policy from approving or
auto-approving the command and makes YOLO mode look like it failed to propagate
approval context.

## What Changes

- Classify direct `python` and `python3` script or code execution as
  `approval_required`.
- Keep Python verification commands such as `pytest`, `ruff`, and `ty` allowed.
- Treat common "run local code" commands across other ecosystems as
  `approval_required` rather than unsupported where they are useful for testing.
- Preserve hard denial for destructive, publishing, mutating, or shell-composed
  commands.

## Impact

- Affected spec: `tools`
- Affected code: `src/deepy/tools/test_shell.py`
- Affected tests: `tests/test_tools.py`, `tests/test_audit.py`
