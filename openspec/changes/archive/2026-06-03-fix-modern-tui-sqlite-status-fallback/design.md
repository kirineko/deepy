## Context

Classic UI and Modern TUI share the same session persistence path through
`run_prompt_once()` and `DeepySession`, so normal conversation storage, usage,
cache-prefix tracking, session cost, and input-suggestion writes are not the
problem.

The divergence is in UI status metadata. Classic UI builds a status footer and
uses a guarded `_session_entry()` helper that catches failures from
`list_session_entries()`. When SQLite cannot be opened for metadata, Classic UI
falls back to unknown context/cache text.

Modern TUI rebuilds status context from `_update_status()`. That path calls
`_tui_session_entry()` for the status bar and `_format_tui_side_status()` for the
side panel. Both can call `list_session_entries()` without a guard, and
`_update_status()` is invoked by high-frequency stream events such as
`text_delta`, `raw_response`, `reasoning_delta`, and tool status changes.

`list_session_entries()` is not a pure read in practice: it opens SQLite and
calls `ensure_schema()`, which sets WAL mode and may create tables or add
columns. Status rendering must therefore avoid treating session-list access as a
cheap, reliable, high-frequency operation.

## Goals / Non-Goals

**Goals:**

- Modern TUI status bar and side panel must degrade when session metadata cannot
  be read from SQLite.
- Modern TUI must avoid repeated session-list reads during high-frequency stream
  status updates.
- Fallback status must remain useful: context should render as unknown and cache
  should render as unavailable/unknown instead of crashing.
- Tests must cover both SQLite-read failure handling and reduced repeated reads
  during stream status updates.

**Non-Goals:**

- Do not change the session database schema.
- Do not change normal session persistence semantics for model turns, usage,
  cache records, input suggestions, session cost, or explicit session commands.
- Do not remove WAL mode or redesign the session store.
- Do not change Classic UI behavior except if shared helper extraction requires
  a behavior-preserving refactor.

## Decisions

### Decision 1: Treat Modern TUI session metadata as best-effort display data

Modern TUI should match Classic UI's tolerance boundary: status metadata reads
must not interrupt rendering. The direct `_tui_session_entry()` lookup should
catch broad exceptions from `list_session_entries()` and return `None`.

Alternative considered: catch only `sqlite3.Error`.

Rationale: the observed failure can surface as `sqlite3.OperationalError`, but
file descriptor exhaustion, permission errors, or filesystem errors can surface
as `OSError` or other exception types. Classic UI already catches broad
exceptions for the same display-only footer path.

### Decision 2: Cache session status metadata inside the Modern TUI app

Modern TUI should keep a small in-memory status metadata snapshot for the active
session. `_update_status()` should render from that cached entry rather than
calling `list_session_entries()` every time a stream event updates the status.

Refresh the snapshot at low-frequency lifecycle points:

- TUI mount or first status render.
- Session id changes after a model turn completes.
- Explicit session actions such as resume, new session, compact, and session
  list/status surfaces where fresh data is expected.
- Usage/cache-affecting lifecycle points after a turn completes or session cost
  records are updated.

During streaming, `_update_status()` should reuse the cached snapshot and should
not refresh SQLite for every token or reasoning delta.

Alternative considered: throttle `list_session_entries()` with a time interval.

Rationale: throttling reduces pressure but still makes status rendering perform
SQLite work during streaming. A lifecycle-refresh model is simpler to test and
fits the fact that context/cache metadata usually changes at turn boundaries, not
per token.

### Decision 3: Keep explicit session commands fresh

Commands and views whose purpose is session inspection or selection may continue
to read the session list directly because they are user-triggered and low
frequency. They should not be part of the stream status hot path.

Alternative considered: route every session-list read through the Modern TUI
cache.

Rationale: `/sessions`, resume pickers, and exit summaries need fresh data and
are not high-frequency. Conflating these with live status rendering risks stale
session-management behavior.

### Decision 4: Prefer localized TUI changes over session-store changes

This change should first fix the UI vulnerability in `src/deepy/tui/app.py`.
Adding a pure read-only session-list API may be a future improvement, but it is
not required to prevent Modern TUI crashes and repeated reads.

Alternative considered: change `list_session_entries()` to use read-only SQLite
mode and skip schema assurance.

Rationale: `list_session_entries()` is used across CLI and UI paths that may
expect schema repair. Changing it globally has broader migration risk. The
reported vulnerability is specifically Modern TUI status rendering.

## Risks / Trade-offs

- Cached context/cache values can be stale during a running stream -> Refresh at
  turn completion and after explicit session lifecycle actions. Streaming status
  can still show token progress independently.
- Broad exception handling can hide unexpected session-list bugs -> Limit the
  broad catch to display-only metadata reads and keep explicit commands/tests
  able to surface failures where appropriate.
- Side panel and status bar can drift if they use different data sources -> Use
  the same cached session entry for both renderers.
- A first status render with an unreadable DB will show unknown values -> This is
  the desired graceful degradation and matches Classic UI behavior.
