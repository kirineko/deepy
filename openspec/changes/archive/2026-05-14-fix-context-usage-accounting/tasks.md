## 1. Regression Coverage

- [x] 1.1 Add a session token-state test proving a short latest usage record does not reduce effective context tokens for unchanged/appended history
- [x] 1.2 Add a runner or compaction-readiness test proving auto compaction still triggers after a shorter follow-up turn when effective context is above threshold
- [x] 1.3 Add a terminal UI test proving bottom `ctx` does not shrink merely because latest API input tokens are smaller
- [x] 1.4 Add restore/migration coverage for stale or missing session index checkpoint metadata
- [x] 1.5 Add compaction reset coverage proving explicit session replacement can lower context tokens and clears pending estimates

## 2. Session Context Accounting

- [x] 2.1 Audit `DeepyJsonlSession` index fields and define the exact meaning of `activeTokens`, `lastUsageTokens`, `pendingTokens`, and `lastUsageRecordCount`
- [x] 2.2 Update `record_usage()` so usage totals remain accumulated while context checkpoints do not reduce effective context tokens on ordinary appended turns
- [x] 2.3 Update append/pop/clear/replace paths so pending token estimates and checkpoint counts stay coherent after history changes
- [x] 2.4 Add stale-index repair or fallback logic in `context_token_state()` when checkpoint metadata is missing, inconsistent, or undercounted
- [x] 2.5 Preserve compatibility with existing session index files without requiring manual deletion

## 3. Compaction And UI Integration

- [x] 3.1 Ensure `ensure_context_ready()` uses effective session context tokens plus current prompt tokens for auto-compaction decisions
- [x] 3.2 Ensure manual and automatic compaction writes a replacement context checkpoint based on compacted summary plus preserved messages
- [x] 3.3 Ensure `_format_context_footer()` reads the same effective token state used by auto compaction
- [x] 3.4 Keep the per-turn usage footer and accumulated session usage display unchanged except where tests require clearer separation

## 4. Verification

- [x] 4.1 Run targeted tests for session JSONL accounting, runner compaction, usage normalization, and terminal UI
- [x] 4.2 Run the broader test subset covering `tests/test_jsonl_session.py`, `tests/test_runner.py`, `tests/test_usage.py`, `tests/test_terminal_ui.py`, and `tests/test_compaction.py`
- [x] 4.3 Manually inspect or simulate the screenshot scenario: large turn followed by `hi` keeps context pressure stable or increasing until explicit compaction
- [x] 4.4 Run `openspec status --change fix-context-usage-accounting` and confirm the change is apply-ready
