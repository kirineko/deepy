## Why

Deepy's bottom `ctx` indicator and automatic compaction readiness can move backward because the session token checkpoint is overwritten with the latest turn's API input tokens. This makes context pressure look smaller after short follow-up turns and can prevent auto compaction from triggering when the persisted session is actually growing.

## What Changes

- Separate per-turn API usage reporting from session context occupancy.
- Make session context occupancy monotonic across normal appended turns, decreasing only when history is explicitly reset, cleared, truncated, or compacted.
- Use effective context tokens, including pending estimated tokens after the latest precise checkpoint, for both bottom toolbar display and auto-compaction decisions.
- Treat provider usage as a precision checkpoint for covered history, not as cumulative cost and not as an unconditional replacement for current context size.
- Preserve the existing per-turn usage footer and accumulated session usage totals as cost/accounting information.
- Add regression coverage for short follow-up turns, multi-request usage, pending messages, restored sessions, and compaction reset behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `session-context`: Clarify that context token accounting is distinct from turn usage accounting, and that automatic compaction must use effective session context tokens rather than the latest turn's total usage.
- `terminal-ui`: Clarify that the bottom context status represents current session context pressure and must not shrink merely because the latest turn was short.

## Impact

- Affected code: `src/deepy/sessions/jsonl.py`, `src/deepy/llm/compaction.py`, `src/deepy/ui/terminal.py`, and tests around usage, context state, runner behavior, and terminal UI.
- Existing session index metadata may contain undercounted `activeTokens`; implementation should be compatible by recomputing or safely repairing stale entries when possible.
- No user-facing command syntax or configuration changes are expected.
- Reference behavior: `reference/kimi-cli` stores context token count separately from pending token estimates and uses `token_count_with_pending` for compaction, while usage records serve as checkpoints rather than user-visible context totals.
