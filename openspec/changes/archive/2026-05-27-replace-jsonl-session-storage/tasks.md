## 1. Storage Boundary And Schema

- [x] 1.1 Add a storage-neutral session module and public exports that no longer expose JSONL-specific names to new call sites.
- [x] 1.2 Add SQLite database path resolution under the existing per-project Deepy session directory.
- [x] 1.3 Implement schema initialization for `sessions`, `session_items`, and compaction archive or snapshot storage.
- [x] 1.4 Add low-level helpers for short-lived SQLite connections, transactions, JSON payload encoding, and row decoding.
- [x] 1.5 Add tests proving a new project initializes an empty transactional session store without reading old JSONL files or `sessions-index.json`.

## 2. Core Session Operations

- [x] 2.1 Implement session create/open and session entry listing from the SQLite store.
- [x] 2.2 Implement item append with ordered sequence numbers, canonical SDK item payload storage, metadata updates, title/status refresh, pending-token updates, and todo-state capture in one transaction.
- [x] 2.3 Implement full and limited item reads so `get_items(limit=N)` reads only the requested tail before replay sanitization.
- [x] 2.4 Implement tail pop for interrupted prompt rollback without replacing precise latest Context Window checkpoints.
- [x] 2.5 Implement clear and replace operations with correct checkpoint resets and preserved metadata.
- [x] 2.6 Port existing SDK replay sanitization, tool-pair, local command transcript, and todo-state tests to the new store.

## 3. Usage, Context, Cost, And Process Metadata

- [x] 3.1 Move accumulated turn usage and latest Context Window checkpoint persistence into the `sessions` table.
- [x] 3.2 Move input suggestion usage persistence into the `sessions` table without affecting ordinary turn usage or Context Window checkpoints.
- [x] 3.3 Move session cost start/end persistence into the `sessions` table.
- [x] 3.4 Move background process metadata and interrupt cleanup persistence into the `sessions` table.
- [x] 3.5 Preserve `ContextTokenState` semantics for checkpoint tokens, pending tokens, record counts, undercount repair, and provider-unknown fallback.
- [x] 3.6 Add regression tests for short latest usage not shrinking effective context, rollback preserving latest Context Window usage, and old JSONL metadata being ignored.

## 4. Compaction Rewrite

- [x] 4.1 Update manual and automatic compaction to read and replace session items through the storage-neutral session API.
- [x] 4.2 Replace JSONL file archive/restore with transactional snapshot/archive and active-history replacement.
- [x] 4.3 Preserve todo state, usage metadata, and compacted Context Window checkpoint after replacement.
- [x] 4.4 Add failure-path tests proving summary-generation failure and replacement-write failure leave the active session unchanged.
- [x] 4.5 Add tests proving compacted sessions remain resumable and replayable after transactional replacement.

## 5. Call Site Migration

- [x] 5.1 Update runner, session manager, status, and input suggestion code to use the storage-neutral session abstraction.
- [x] 5.2 Update stable terminal UI `/resume`, `/sessions`, `/compact`, local command mode, history rendering, status, and exit-summary paths.
- [x] 5.3 Update experimental Textual TUI session list, resume, transcript restore, compact, local command mode, status, and exit-summary paths.
- [x] 5.4 Update CLI `deepy sessions list` and `deepy sessions show` to read from the transactional store.
- [x] 5.5 Remove JSONL/index compatibility code and tests that are no longer part of the contract.

## 6. Documentation And Validation

- [x] 6.1 Update user-facing documentation or release notes to state that historical JSONL sessions are not migrated or listed after this breaking storage change.
- [x] 6.2 Run `openspec validate replace-jsonl-session-storage --type change --strict`.
- [x] 6.3 Run focused session, context, compaction, local command, terminal UI, TUI, status, and input suggestion tests.
- [x] 6.4 Run `uv run ruff check src tests`.
- [x] 6.5 Run `uv run ty check src`.
- [x] 6.6 Run `uv run pytest`.
