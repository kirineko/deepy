## Why

Deepy's current session persistence splits canonical replay items across per-session
JSONL files while storing derived state in `sessions-index.json`. That split makes
context checkpoints, compact rewrites, resume previews, todo state, usage, cost,
and process cleanup depend on fragile dual writes and repeated full-history reads.

The user has explicitly allowed dropping historical JSONL compatibility. That
creates room to replace the format with a simpler, transactional local store
instead of carrying legacy storage constraints into future context and compact
work.

## What Changes

- **BREAKING**: Stop reading and writing historical JSONL session files and
  `sessions-index.json` as the active session store.
- Replace the active project session store with a transactional local SQLite
  database that keeps session metadata and ordered replay items together.
- Preserve the public session behavior: new sessions, resume selection,
  `deepy sessions list`, `deepy sessions show`, prompt replay, local command
  transcripts, input suggestions, todo state, usage, session cost, interrupt
  rollback, and manual/automatic compaction remain available.
- Store replayable OpenAI Agents SDK items as the canonical per-item payload so
  model continuation does not depend on display-only history records.
- Move context checkpoint metadata, pending token estimates, latest Context
  Window usage, accumulated usage, input suggestion usage, todo state, session
  cost, and process metadata into the same transactional store.
- Replace file-level compaction archive/rewrite with transactional snapshot or
  archive semantics that cannot leave the active session partially rewritten.
- Rename or wrap the existing `DeepyJsonlSession` implementation boundary so
  callers use a storage-neutral session abstraction.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `session-context`: Replace the JSONL session-format contract with a
  transactional local session store contract, while preserving replay, context
  accounting, compaction, todo, local command, and usage semantics.
- `terminal-ui`: Keep stable terminal session commands and history rendering
  behavior unchanged across the storage replacement.
- `experimental-textual-tui`: Keep TUI session lifecycle, resume, compact, and
  restored transcript behavior unchanged across the storage replacement.

## Impact

- Affected code:
  - `src/deepy/sessions/jsonl.py`
  - `src/deepy/sessions/__init__.py`
  - `src/deepy/sessions/manager.py`
  - `src/deepy/llm/runner.py`
  - `src/deepy/llm/compaction.py`
  - `src/deepy/status.py`
  - `src/deepy/ui/terminal.py`
  - `src/deepy/tui/app.py`
  - session, context, compact, terminal UI, TUI, local command, input suggestion,
    status, and cost tests
- Dependencies:
  - Use Python's standard-library `sqlite3`; no new runtime dependency is
    expected.
- Data compatibility:
  - Existing JSONL sessions and `sessions-index.json` are not migrated or read
    by the new active store.
- User-visible behavior:
  - Existing session commands remain, but only sessions in the new store are
    listed or resumed after the change.
