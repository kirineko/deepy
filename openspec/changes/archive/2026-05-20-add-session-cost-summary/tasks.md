## 1. Balance Cost Model

- [x] 1.1 Add a Decimal-based session cost data model for balance snapshots, per-currency deltas, unavailable reasons, and display-safe formatting.
- [x] 1.2 Reuse the existing DeepSeek balance response parser for snapshot capture without exposing API keys in errors or rendered text.
- [x] 1.3 Add tests for positive spend, zero spend, balance increases, currency mismatch, invalid decimal strings, and unavailable snapshots.

## 2. Session Persistence

- [x] 2.1 Extend session index entries with optional cost snapshot metadata while keeping existing indexes readable.
- [x] 2.2 Add session helpers to record starting snapshot, ending snapshot, computed spend, and unavailable reason.
- [x] 2.3 Ensure cost metadata does not affect Token Usage merging, latest Context Window usage, active token estimates, or compaction checkpoints.
- [x] 2.4 Add session persistence tests for new metadata, absent metadata, and backward-compatible index loading.

## 3. Interactive Snapshot Flow

- [x] 3.1 Record a start balance snapshot for stable interactive sessions when a session becomes cost-trackable.
- [x] 3.2 Record an end balance snapshot during stable `/exit`, `/quit`, and confirmed Ctrl+D shutdown before rendering the summary.
- [x] 3.3 Wire the same start/end snapshot lifecycle into experimental Textual TUI exit paths after returning terminal control.
- [x] 3.4 Keep startup, welcome, footer/status bar, model turns, usage footers, input suggestions, and non-exit surfaces free of balance calls.

## 4. Exit Summary Rendering

- [x] 4.1 Update `build_exit_summary_text()` to render a concise session cost row when a reliable balance delta exists.
- [x] 4.2 Render concise cost unavailable text when cost tracking was attempted but no reliable delta can be computed.
- [x] 4.3 Label the value as a DeepSeek account balance delta during the session without overclaiming exclusive Deepy spend.
- [x] 4.4 Preserve existing model usage, suggestion usage, model, session, and no-usage summary behavior.

## 5. Validation

- [x] 5.1 Add focused tests for stable terminal exit summaries with successful cost, unavailable cost, and no API key.
- [x] 5.2 Add focused tests for experimental Textual TUI exit summaries with successful and unavailable cost.
- [x] 5.3 Update existing no-balance-fetch tests so they still cover non-status and non-exit surfaces.
- [x] 5.4 Run focused tests for status, sessions, exit summary, stable terminal UI, and Textual TUI.
- [x] 5.5 Validate the OpenSpec change with `openspec validate add-session-cost-summary --type change --strict`.
