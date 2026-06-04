## 1. Modern TUI Session Metadata Fallback

- [x] 1.1 Add a Modern TUI session metadata helper or cache field that returns `None` when `list_session_entries()` raises.
- [x] 1.2 Update status bar context rendering to use the safe cached session metadata instead of directly reading the session list.
- [x] 1.3 Update side-panel status rendering to use the same safe cached session metadata instead of performing a second direct session-list read.
- [x] 1.4 Ensure fallback rendering shows unknown/unavailable context and cache values without raising through the Textual message loop.

## 2. Reduce High-Frequency SQLite Access

- [x] 2.1 Introduce lifecycle-based refresh points for the cached session metadata, including TUI mount, session id changes, turn completion, resume/new session, compaction, and session cost updates.
- [x] 2.2 Ensure stream-event status updates such as text deltas, reasoning deltas, raw response updates, tool calls, and tool outputs reuse cached session metadata.
- [x] 2.3 Keep explicit low-frequency session commands and summaries able to read fresh session data when their purpose is session inspection or selection.

## 3. Regression Tests

- [x] 3.1 Add a Modern TUI status-context test where `list_session_entries()` raises `sqlite3.OperationalError` and the status output falls back instead of raising.
- [x] 3.2 Add a Modern TUI side-panel status test where session metadata read failure renders fallback cache/session metadata instead of raising.
- [x] 3.3 Add a stream-status update test that emits multiple status-changing stream events and verifies session-list reads are not performed once per event.
- [x] 3.4 Run focused tests for Modern TUI status rendering and session metadata behavior.
