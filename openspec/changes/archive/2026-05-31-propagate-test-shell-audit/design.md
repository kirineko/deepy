## Context

`tester` subagents are intentionally limited to `test_shell` for command-based
verification. Today `test_shell` has its own token retry path for medium-risk commands:
the tool returns `approval_required`, the subagent reports that to the main agent, and the
main agent must ask the user and retry with a token. This keeps raw shell away from the
subagent, but it bypasses the existing SDK approval interruption lifecycle used by Deepy's
audit UI.

The observed failure is `cargo run`: the tester subagent cannot execute it, the outer audit
surface never sees a pending command approval, and the main agent compensates by running raw
`shell` itself.

## Goals / Non-Goals

**Goals:**

- Make medium-risk `test_shell` commands participate in the outer SDK audit lifecycle.
- Preserve the constrained `test_shell` classifier and runner after approval.
- Treat `cargo run` as medium-risk because it executes project code.
- Keep hard-denied commands denied before any approval prompt.

**Non-Goals:**

- Do not expose raw `shell` to tester subagents.
- Do not turn all unsupported commands into approval prompts.
- Do not change SDK approval handling for regular `shell`, text writes, MCP, or task control.

## Decisions

- Add a `needs_approval` callback to the `test_shell` FunctionTool. It will parse the
  requested command using the existing `test_shell` classifier and return true only when the
  command is classified `approval_required` and the active audit mode requires command approval.
  This reuses the SDK interruption path already handled by the terminal and TUI.
- Add an explicit audit-approved execution path to `ToolRuntime.test_shell` and
  `run_test_shell_command`. The runner will still deny destructive or unsupported commands,
  but an `approval_required` command may execute when it has either a legacy token or an active
  audit-policy-backed invocation.
- Preserve the legacy token path when no audit policy is supplied. This avoids breaking tests or
  direct callers that still rely on structured `approval_required` results.
- Classify `cargo run` as `approval_required`. `cargo test`, `cargo check`, and `cargo clippy`
  remain low-risk allowed verification commands.

## Risks / Trade-offs

- SDK approval does not pass an explicit "approved" flag into the tool invocation. Mitigation:
  only the function tool wrapper will mark `test_shell` as audit-approved, and only when an
  audit policy is present; the SDK already prevents invocation until approval in normal/auto
  modes, while yolo mode intentionally auto-approves side effects.
- Some medium-risk commands may now execute automatically in yolo mode instead of returning a
  token. Mitigation: yolo already means auto-approve side effects, and hard-denied commands
  remain denied by `test_shell` policy.
- Approval UI may label the pending tool as `test_shell` rather than raw `shell`. Mitigation:
  the arguments still include the exact command, and the tool remains constrained.
