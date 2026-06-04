## Why

Deepy's current context management has to be treated as a defective implementation, not as a base to extend. Automatic compacting only trims model input through the Agents SDK session callback, while persisted history remains uncompressed. The manual compaction helper clears useful history and replaces it with a placeholder. Token accounting also misses messages appended after the latest model usage update, so large tool results can push the next request past the window without triggering compaction.

This change replaces that whole compact/context path with a durable session-level context state machine, following the Kimi CLI pattern of manual `/compact`, auto compaction, pending-token accounting, reserved output budget, and safe history rotation.

## What Changes

- Replace the old context trimming and placeholder compaction code path with a new context state/compaction subsystem.
- Add a user-facing `/compact [focus]` command that compacts the active session with an optional focus instruction.
- Generate model-written summaries and preserve recent valid conversation/tool-call groups after the summary.
- Preserve recoverability by archiving the pre-compaction session before rewriting active history.
- Run durable auto compaction before model calls when context pressure exceeds policy.
- Add pending-token accounting so messages appended after the last model usage update contribute to auto compact decisions.
- Add reserved-context budgeting so Deepy compacts when remaining space is too small for the next response, even if the ratio threshold is not yet crossed.
- Stop treating transient input trimming as compaction; oversized context that cannot be compacted must fail visibly instead of silently dropping history.
- Update context status, session listings, and usage accounting so active context tokens reflect compacted summaries and pending estimates.
- Add tests for manual compaction, auto compaction triggers, session rewrite recoverability, token accounting, removal of legacy trim behavior, and UI command behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `session-context`: Define durable manual and automatic compaction, pending-token accounting, reserved context thresholds, history rotation, and retirement of legacy input-trim behavior.
- `terminal-ui`: Add `/compact` command discoverability, execution feedback, empty-session handling, and refreshed context status.
- `configuration`: Add canonical context compaction policy settings and deprecate legacy compact threshold semantics where they conflict with the new policy.

## Impact

- Affected runtime modules: `src/deepy/llm/context.py`, `src/deepy/llm/runner.py`, `src/deepy/sessions/jsonl.py`, `src/deepy/sessions/manager.py`, and `src/deepy/prompts/compact.py`.
- Affected UI modules: `src/deepy/ui/slash_commands.py`, `src/deepy/ui/terminal.py`, status/footer rendering, session list/resume display, and welcome/help command text.
- Affected configuration: `src/deepy/config/settings.py`, config serialization, `deepy config show`, `deepy doctor`, README config examples.
- Affected tests: context estimation, session persistence, runner callback behavior, slash commands, terminal UI, settings, status, and failure recovery.
- The old compact behavior is intentionally not preserved. Existing session JSONL should remain readable, but old placeholder compaction records and old context estimates are migrated or ignored rather than treated as authoritative.
