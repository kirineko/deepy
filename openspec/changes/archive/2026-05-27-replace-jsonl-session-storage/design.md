## Context

Deepy currently implements the OpenAI Agents SDK session protocol through
`DeepyJsonlSession`. The class appends SDK replay items to `<session>.jsonl`,
stores derived metadata in `sessions-index.json`, and exposes helper methods for
usage, context checkpoints, todo state, session cost, process tracking, and
history rewrites.

That layout has become a shared bottleneck. The JSONL file is append-friendly, but
resume previews, `ctx`, compaction readiness, todo restoration, cost summaries,
and background-process cleanup all depend on keeping a second index file
coherent. Some operations also rewrite or reread the full session file:
`get_items(limit=...)` loads all items before slicing, `pop_item()` rewrites the
file after tail rollback, and compaction rotates the JSONL file before writing a
replacement.

Historical JSONL compatibility is explicitly out of scope for this change. The
new store can therefore optimize for the current Deepy contract rather than
carrying legacy record-shape adapters.

## Goals / Non-Goals

**Goals:**

- Replace the active JSONL/index session store with one transactional local
  SQLite database per project.
- Preserve the public behavior of session commands, replay, local command
  transcripts, input suggestions, todo state, context accounting, cost summaries,
  interrupt rollback, and manual/automatic compaction.
- Keep replayable Agents SDK items as the canonical stored conversation payload.
- Make metadata and items update atomically so derived session state cannot drift
  from replay history.
- Support efficient latest-N history reads for resume and TUI restoration without
  loading the entire session.
- Keep the implementation storage-neutral at call sites so future changes do not
  expose a JSONL-specific class name.

**Non-Goals:**

- Migrating, importing, or reading existing JSONL sessions.
- Introducing a server, daemon, or networked storage backend.
- Changing OpenAI Agents SDK item semantics or provider usage normalization.
- Changing the user-facing syntax of `/resume`, `/compact`, `/sessions`,
  `deepy sessions list`, or `deepy sessions show`.
- Adding a new runtime dependency beyond Python's standard-library `sqlite3`.

## Decisions

### 1. Use SQLite as the active project session store

Store each project's sessions in a single SQLite database under the existing
project session directory, for example:

```
~/.deepy/projects/<project-code>/sessions.db
```

Minimum schema shape:

```
sessions(
  id text primary key,
  created_at integer not null,
  updated_at integer not null,
  item_count integer not null,
  active_tokens integer not null,
  latest_context_window_tokens integer,
  last_usage_tokens integer,
  pending_tokens integer not null,
  last_usage_record_count integer,
  usage_json text,
  input_suggestion_usage_json text,
  todo_state_json text,
  session_cost_json text,
  processes_json text,
  title text,
  status text
)

session_items(
  session_id text not null,
  seq integer not null,
  created_at integer not null,
  role text not null,
  item_type text,
  payload_json text not null,
  primary key(session_id, seq)
)

session_archives(
  id text primary key,
  session_id text not null,
  created_at integer not null,
  reason text not null,
  before_tokens integer not null,
  after_tokens integer,
  item_snapshot_json text not null
)
```

Indexes should support listing sessions by `updated_at` and reading items by
`session_id, seq`.

Alternative considered: keep JSONL and replace only `sessions-index.json` with
SQLite. Rejected because it keeps the two-source model and does not solve
transactional compaction, tail rollback, or efficient latest-N reads cleanly.

Alternative considered: one SQLite database per session. Rejected because session
listing and project-wide status would still need a separate catalog or filesystem
scan.

### 2. Store SDK replay payloads directly

`session_items.payload_json` stores the original replayable SDK item. Columns such
as `role` and `item_type` are derived indexes for quick filtering and preview
building, not alternate sources of truth.

When reading items for model replay, Deepy decodes payloads and applies the
existing replay sanitization rules. When rendering history, Deepy uses the same
decoded SDK items that would be replayed to the model.

Alternative considered: normalize every message and tool call into relational
columns. Rejected because the Agents SDK item surface is flexible and preserving
the exact replay item reduces schema churn.

### 3. Introduce a storage-neutral session boundary

Replace call-site dependency on `DeepyJsonlSession` with a storage-neutral class,
for example `DeepySession`, backed by an internal `SqliteSessionStore`.

The public methods should preserve the existing behavioral shape:

- `create()`, `open()`
- `get_items(limit=None)`, `get_items_sync(limit=None)`
- `add_items()`
- `pop_item()`
- `clear_session()`
- `replace_items()`
- `record_usage()`
- `record_input_suggestion_usage()`
- `record_session_cost_start()`
- `record_session_cost_end()`
- `session_cost()`
- `context_token_state()`
- `latest_context_window_usage()`
- `todo_state()`
- `list_session_entries()`

The old JSONL-specific class may remain temporarily as an import alias only if it
reduces implementation risk, but new code should not expose JSONL in names,
documentation, specs, or tests.

Alternative considered: rewrite all callers directly against a lower-level store.
Rejected because the Agents SDK expects a session-like object and current callers
already have a useful boundary.

### 4. Use transactions for append, metadata, rollback, and compaction

Every mutating operation that changes items and metadata should run in a SQLite
transaction:

- `add_items()` inserts item rows, updates `item_count`, `updated_at`, pending
  token estimates, title/status previews, and latest todo state.
- `record_usage()` updates accumulated usage and context checkpoint fields
  without mutating item rows.
- `pop_item()` deletes only the final item row and updates internal active-token
  metadata while preserving latest request Context Window checkpoints according
  to the existing rollback contract.
- `replace_items()` deletes old active rows, inserts replacement rows, resets
  checkpoint fields, and preserves metadata that must survive compaction.
- `clear_session()` empties item rows and resets relevant metadata.

Compaction should generate the summary before opening the replacement
transaction. Once the replacement is ready, the transaction snapshots the current
items into `session_archives`, replaces the active item rows, and updates metadata
atomically. If any write fails, the transaction rolls back and the active session
remains unchanged.

Alternative considered: use a temporary database file and file rename for
compaction. Rejected because SQLite transactions already provide the needed
atomicity without extra file choreography.

### 5. Preserve context semantics exactly while changing storage

The storage replacement must not collapse the existing accounting boundary:

- accumulated `TokenUsage` remains API cost/telemetry;
- `latest_context_window_tokens` remains latest request Context Window occupancy;
- `active_tokens`, `last_usage_tokens`, `pending_tokens`, and
  `last_usage_record_count` remain the effective context-pressure state used for
  compaction decisions and safe fallbacks;
- input suggestion usage remains separate from ordinary turn usage and must not
  update Context Window checkpoints.

Because the store can query item counts cheaply, `last_usage_record_count` may
continue to mean "number of stored replay items covered by the checkpoint".

Alternative considered: recompute active tokens from all stored rows on every
read. Rejected as the primary path because prior context work deliberately uses
provider checkpoints plus pending estimates to avoid drift and unnecessary full
history scans.

### 6. Do not migrate old JSONL sessions

After this change, listing and resume commands only see sessions in the new
SQLite store. Existing JSONL files and `sessions-index.json` may remain on disk
but are ignored by the active code path.

This is a breaking change but matches the requested scope. It also avoids a large
migration layer that would preserve the historical compatibility burden this
change is meant to remove.

## Risks / Trade-offs

- SQLite database corruption or interrupted writes -> Use transactions, leave
  SQLite journaling enabled, and add tests that simulate failed compaction
  replacement writes.
- Breaking existing local sessions -> This is intentional and documented in the
  proposal; release notes should call out that old JSONL sessions are not
  imported.
- Cross-platform filesystem locking differences -> Keep connections short-lived
  for CLI/TUI operations and test on Windows-sensitive paths where practical.
- Larger implementation diff across many modules -> First preserve the existing
  session API shape, then update imports and tests incrementally.
- JSON payloads inside SQLite are less inspectable than JSONL -> Keep
  `deepy sessions show` as the supported inspection surface.
- Compaction archive snapshots can grow the database -> Keep archives bounded or
  make retention explicit if database growth becomes an issue; do not add
  retention behavior in this first change unless required by tests.

## Migration Plan

1. Add SQLite store helpers and schema initialization under `src/deepy/sessions/`.
2. Introduce the storage-neutral session class while preserving the current
   method surface used by runner, compaction, UI, TUI, status, and tests.
3. Move session metadata reads/writes from `sessions-index.json` into SQLite.
4. Move replay item append/read/pop/replace/clear from JSONL files into
   `session_items`.
5. Replace compaction file archive/rewrite with transactional snapshot and
   replacement.
6. Update public imports and tests away from JSONL-specific naming.
7. Remove tests that assert legacy JSONL compatibility; replace them with tests
   proving old JSONL files are ignored.
8. Run focused session/context/compact/UI/TUI tests, then the standard quality
   gate.

Rollback strategy during development is to revert the change before release. Once
released, rollback would reintroduce JSONL storage but would not recover sessions
created only in the SQLite store unless a separate export/import tool is built,
which is out of scope.

## Open Questions

- Should `session_archives` keep every compacted snapshot indefinitely, or should
  the first implementation expose a small retention limit?
- Should the SQLite database filename be `sessions.db` or a versioned name such
  as `sessions-v3.db` to make the breaking storage boundary clearer on disk?
