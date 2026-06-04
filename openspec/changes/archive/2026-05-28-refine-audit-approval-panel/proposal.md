## Why

The current audit approval panel exposes SDK-shaped fields such as `action`,
`tool`, `agent`, and `arguments.*`, which makes the panel feel like a debug
dump instead of a concise decision prompt. Recent interactive testing also
showed that users need stronger visual focus on the target command or file
diff before approving side effects.

## What Changes

- Replace raw argument-field approval panels with task-focused summaries for
  shell commands, file writes/updates, MCP tools, and fallback tool calls.
- Render `Write` and `Update` approvals with highlighted diff previews, using
  project-relative paths when a project root is available.
- Add a non-decision expand/collapse control for truncated diffs, visually
  separated above the final `Approve` / `Reject` decision area.
- Restrict approval selection shortcuts to `Up` / `Down` navigation, `Enter`
  activation, and `Esc` rejection.
- Remove letter shortcuts such as `Y`, `A`, `N`, and `R` from the approval
  picker and from visible approval hints.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: refine stable terminal approval prompt rendering and keyboard
  interaction requirements.

## Impact

- Affected code:
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/audit_approval_picker.py`
  - potentially `src/deepy/ui/message_view.py` if existing diff preview helpers
    need a reusable approval-specific adapter
- Affected tests:
  - `tests/test_terminal_ui.py`
  - `tests/test_audit_approval_picker.py`
- Affected docs:
  - `docs/deepy-ui-and-tui.md`
  - `docs/deepy-ui-and-tui.zh-CN.md`
- No provider, OpenAI Agents SDK, MCP policy, or persisted configuration
  behavior changes are intended.
