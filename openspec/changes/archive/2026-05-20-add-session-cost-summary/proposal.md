## Why

Deepy already shows DeepSeek account balance on demand in `/status`, but users
cannot see how much a completed interactive session cost when they exit. Showing
a session-scoped cost summary in the exit panel closes that feedback loop using
the provider's real balance data instead of a fragile token-price estimate.

## What Changes

- Capture DeepSeek balance snapshots around an interactive session when an
  official DeepSeek API key is configured.
- Compute per-currency session spend from the difference between starting and
  ending `total_balance` values.
- Show the computed session cost in stable and experimental exit summary panels
  while preserving existing local Token Usage rows.
- Degrade gracefully when balance lookup is unavailable, malformed, or cannot
  produce a reliable delta.
- Document that the value is an account balance delta during the session and may
  include external account activity if the same DeepSeek account is used
  concurrently elsewhere.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deepseek-provider`: Extend balance lookup usage from `/status`-only to
  deliberate session cost snapshots while preserving short timeouts and secret
  safety.
- `session-context`: Persist session cost snapshot metadata separately from
  Token Usage and Context Window accounting.
- `terminal-ui`: Show session cost in stable exit summaries and update the
  existing exit-summary contract that currently forbids balance display.
- `experimental-textual-tui`: Show the same session cost information in the
  experimental TUI exit summary after leaving the full-screen app.

## Impact

- Affected code:
  - `src/deepy/status.py`
  - `src/deepy/sessions/jsonl.py`
  - `src/deepy/ui/exit_summary.py`
  - `src/deepy/ui/terminal.py`
  - `src/deepy/tui/app.py`
  - focused tests for status, sessions, exit summary, stable terminal UI, and
    Textual TUI exit behavior
- Affected systems:
  - Stable interactive terminal exit flow
  - Experimental Textual TUI exit flow
  - Session index metadata
  - DeepSeek balance endpoint usage
- No public CLI flags, configuration keys, or third-party dependencies are
  expected.
