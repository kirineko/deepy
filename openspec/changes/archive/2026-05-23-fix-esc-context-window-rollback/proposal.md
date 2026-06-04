## Why

Pressing Esc immediately after submitting a prompt can make the prompt footer jump
from a correct latest-request Context Window value such as `119K/1M` to an
impossible value such as `3M/1M`. The investigation showed that the interrupted
user-input rollback path can persist internal active-token estimates into the
`latestContextWindowTokens` field, which the footer treats as precise latest
request context occupancy.

## What Changes

- Preserve latest-request Context Window checkpoints when an interrupted turn
  rolls back only the newly persisted user input.
- Keep internal active-token estimates separate from user-facing
  `latestContextWindowTokens` except for explicit history rewrites such as
  compaction.
- Ensure Esc interruption handling does not overwrite precise provider usage
  checkpoints with local cumulative history estimates.
- No breaking changes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `session-context`: Clarify that rollback of an interrupted prompt must not
  replace the latest request Context Window checkpoint with internal
  active-token estimates.
- `terminal-ui`: Clarify that the prompt footer must remain tied to the latest
  request Context Window checkpoint after an Esc-only prompt rollback.

## Impact

- Affected code paths:
  - `src/deepy/llm/runner.py` interruption reconciliation.
  - `src/deepy/sessions/jsonl.py` session mutation and index checkpoint updates.
  - `src/deepy/ui/terminal.py` context footer rendering, if fallback behavior
    needs adjustment.
- Affected tests:
  - `tests/test_jsonl_session.py`
- No external API or dependency changes.
