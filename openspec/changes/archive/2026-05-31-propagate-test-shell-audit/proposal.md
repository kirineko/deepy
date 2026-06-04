## Why

Tester subagents currently receive only `test_shell`, but medium-risk verification commands
such as `cargo run` are handled as in-band `approval_required` tool results. That leaves the
outer Deepy audit UI unaware of the requested command, so the main agent may work around the
subagent with raw `shell` instead of preserving the intended constrained execution path.

## What Changes

- Route `test_shell` commands classified as `approval_required` through the outer SDK audit
  interruption lifecycle when an audit policy is active.
- Execute an approved medium-risk `test_shell` command through the same constrained
  `test_shell` runner, not raw `shell`.
- Classify Rust `cargo run` as a medium-risk verification command that requires audit approval
  rather than as an unsupported denial.
- Keep destructive, publishing, mutating, shell-composition, and unsupported commands denied by
  `test_shell` policy.

## Capabilities

### New Capabilities

### Modified Capabilities

- `subagents`: tester subagent command approvals must surface through the outer audit flow.
- `tools`: `test_shell` medium-risk command behavior changes from in-band token-only approval to
  SDK audit-backed approval when an audit policy is active.
- `system-audit`: command approval requirements include subagent-originated medium-risk
  constrained verification commands.

## Impact

- Affected implementation: `src/deepy/tools/agents.py`, `src/deepy/tools/builtin.py`,
  `src/deepy/tools/test_shell.py`.
- Affected prompts/docs: `src/deepy/prompts/system.py`, `src/deepy/data/tools/test_shell.md`,
  `docs/subagents.md`, `docs/subagents.zh-CN.md`.
- Affected tests: focused tests for `test_shell` classification and audit policy integration.
