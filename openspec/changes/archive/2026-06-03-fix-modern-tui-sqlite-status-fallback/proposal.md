## Why

Modern TUI status rendering currently treats session SQLite reads as a hard dependency. When the session database cannot be opened for status metadata, the Textual message loop can crash during normal streaming updates instead of degrading like the Classic UI.

The issue is amplified because Modern TUI rebuilds status and side-panel session context on high-frequency stream events, causing repeated `list_session_entries()` calls that may open SQLite and run schema/WAL setup work.

## What Changes

- Make Modern TUI session status metadata best-effort: SQLite/session-list failures must not crash status bar, side panel, streaming output, or turn completion UI.
- Align Modern TUI fallback behavior with Classic UI by showing unknown context/cache values when session metadata cannot be read.
- Reduce high-frequency SQLite access from Modern TUI status updates by caching session status metadata and refreshing it only at meaningful lifecycle points.
- Keep normal session persistence unchanged for conversation items, usage, cache prefix records, input suggestions, session cost, and explicit session commands.
- Add regression coverage for SQLite failures in Modern TUI status rendering and for reduced repeated session-list reads during streaming status updates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `experimental-textual-tui`: Modern TUI status and side-panel session metadata must tolerate session SQLite read failures and avoid high-frequency repeated session-list reads.

## Impact

- Affected code:
  - `src/deepy/tui/app.py`
  - Modern TUI tests in `tests/test_tui_app.py`
- Related behavior:
  - `src/deepy/ui/terminal.py` remains the reference for graceful footer fallback.
  - `src/deepy/sessions/index.py` and session persistence should not need behavioral changes for this fix.
- No CLI arguments, config keys, external APIs, or dependencies are expected to change.
