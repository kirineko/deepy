## 1. Session Checkpoint Semantics

- [x] 1.1 Update `DeepyJsonlSession.pop_item()` so ordinary tail rollback preserves the existing `latestContextWindowTokens` checkpoint instead of replacing it with `activeTokens`.
- [x] 1.2 Keep `activeTokens`, `lastUsageTokens`, `pendingTokens`, and `lastUsageRecordCount` updates intact after rollback so compaction pressure remains conservative.
- [x] 1.3 Preserve explicit rewrite semantics for `replace_items()` and `clear_session()` so compaction and new-session flows can still reset Context Window checkpoints.

## 2. Test Updates

- [x] 2.1 Update existing tests that incorrectly assumed `pop_item()` should reset latest Context Window usage from active-token estimates.
- [x] 2.2 Avoid adding dedicated regression tests for this narrow rollback bug after confirming the fix with focused checks.

## 3. Validation

- [x] 3.1 Run focused checks for the adjusted JSONL session semantics and affected test files.
- [x] 3.2 Run `openspec validate fix-esc-context-window-rollback --type change --strict`.
- [x] 3.3 Run the repo's standard lightweight quality checks needed for this scoped bugfix.
