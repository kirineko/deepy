## Why

Successful subagent runs can return reports that mention rejected audit approvals or other rejection-related findings. The stable terminal UI currently scans the raw tool-output JSON for rejection phrases, so it can render a successful subagent result as `[Subagent] <name> rejected`.

## What Changes

- Treat audit-rejection rendering as a status of the returned tool result, not as a substring match across successful structured output.
- Keep explicit SDK audit-rejection tool outputs rendered as rejected.
- Add regression coverage for successful subagent output whose report text mentions audit approval rejection.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Clarify that successful structured subagent results must render as successful even when their report text discusses a rejected approval.

## Impact

- Affects stable terminal UI stream rendering in `src/deepy/ui/terminal.py`.
- Adds focused terminal UI tests in `tests/test_terminal_ui.py`.
- No API, dependency, or storage changes.
