## Context

Deepy's current file mutation layer exposes four model-facing tools:
`read_file`, `edit_text`, `write_file`, and structured `apply_patch`. The
runtime behind those tools already has useful safety behavior: workspace path
resolution, mutation policy checks, text-target classification, encoding and
line-ending preservation, stale write detection, atomic writes, and diff
metadata. The problem is the model-facing API shape, not the safety primitives.

The screenshots that motivated this change show two representative failures:
one stale file in a multi-file `apply_patch` batch rejected all edits, and a
model used `old_str`/`new_str` instead of the required `old_text`/`new_text`.
Both failures came from tool-surface complexity. More repair logic would reduce
some symptoms, but it would keep the model reasoning about patch operation
types, nullable required fields, freshness tokens, and overlapping edit tools.

This change intentionally aligns with the same release window as the
session/history storage rewrite. Old histories and old file-tool calls are not
compatibility targets for this change.

## Goals / Non-Goals

**Goals:**

- Make `Read`, `Write`, and `Update` the only model-facing built-in file tools
  for new agent runs.
- Reduce model pre-call thinking by making the edit choice obvious: read
  context, write whole content, or update exact text.
- Improve throughput by allowing `Read` to load multiple files/ranges
  concurrently in one tool call.
- Improve mutation throughput by allowing `Update` to apply multiple exact
  replacements across one or more files in one call.
- Keep file mutation safety checks inside the runtime rather than exposing
  snapshot ids, snapshot tokens, or content hashes to the model.
- Make UI/TUI output match the new canonical tool names and hide obsolete
  patch/edit labels from new runs.

**Non-Goals:**

- No compatibility shim for executing `read_file`, `edit_text`, `write_file`, or
  `apply_patch` in new model runs.
- No guarantee that old session/history transcripts containing old file-tool
  calls render or resume cleanly.
- No fuzzy/semantic code editing in `Update`; it remains exact text replacement
  with diagnostics.
- No general file management replacement for delete/move/copy workflows in this
  change. Those remain outside the v3 Read/Write/Update core unless implemented
  later as separate tools or shell workflows.

## Decisions

### 1. Use a breaking v3 tool surface instead of aliases

The model-facing names will be `Read`, `Write`, and `Update`. Old snake-case
tools will not be registered for new runs.

Alternatives considered:

- Keep old tools and add aliases. This preserves compatibility but leaves the
  model with more choices and keeps old schema shapes in the cache prefix.
- Rename only `apply_patch` to `Update`. This does not solve nullable fields,
  operation-type branching, or stale multi-file patch behavior.

### 2. Let `Read` support both single-target and batch reads

`Read` will accept either a single `path` with optional range controls or a
`files` array of read targets. The runtime will resolve and read independent
targets concurrently, then return per-target results and aggregate metadata.
Text reads continue to return line-numbered content, total line counts,
truncation state, and managed read-state metadata.

The intended common calls are short:

```json
{"path":"src/app.py"}
```

```json
{"files":[{"path":"src/app.py"},{"path":"tests/test_app.py","range":"20-120"}]}
```

### 3. Make `Update` the only exact replacement mutation tool

`Update` will accept a single file with `old`/`new`, a single file with an
`edits` array, or a top-level `edits` array where each edit names its target
path. The runtime normalizes these shapes into an ordered edit list, groups
edits by file, preflights all edits, and commits only after validation succeeds.

Canonical edit fields are `old`, `new`, `replace_all`, and
`expected_occurrences`. The schema and docs will not expose `old_text`,
`new_text`, `old_string`, `new_string`, `search`, or `replace` as canonical
fields.

### 4. Hide freshness tokens from the model

The v2 tools exposed `snapshot_id`, `snapshot_token`, and `expected_hash` so the
model could prove freshness. In v3, `Read` records runtime-managed read state
and `Write`/`Update` consult that state directly. If a target file is stale or
unread, the mutation tool returns a concise re-read error instead of asking the
model to copy a token.

This preserves safety while removing a frequent source of argument mistakes.

### 5. Keep mutation commits atomic at the tool-call level

`Update` will preflight every edit in the call before writing any file. If a
validation failure occurs, no file is changed. If a late disk write failure
occurs after writing begins, Deepy will return partial/rollback metadata. The
implementation should prefer staging new content per file and using existing
atomic write helpers; if multiple files are committed and a late write fails,
best-effort rollback or backup metadata must be reported.

This keeps behavior predictable: one `Update` call either succeeds as a logical
unit or clearly reports what happened.

### 6. Remove structured apply-patch from the default tool contract

The structured patch parser and tests may be deleted or left as private helper
code only if it is no longer registered, documented, or referenced by the model
prompt. The canonical OpenSpec contract after archive should not describe
`apply_patch` as available to the model.

### 7. Treat prompt/cache changes as an intentional prefix reset

Tool definitions are part of DeepSeek cache-prefix snapshots. This change will
alter the stable prefix once. After the release, `Read`/`Write`/`Update` tool
definitions and docs become the canonical stable prefix. Compaction should use
the same provider/model and same tool definition snapshot as the main agent, but
its instructions continue to forbid tool calls.

## Risks / Trade-offs

- **Risk: removing `apply_patch` loses create/delete/move convenience.**  
  Mitigation: scope v3 to the file read/write/update path requested here; use
  `Write` for creation and shell or future focused tools for file management.

- **Risk: batch `Update` can still fail all edits because one edit is stale or
  unmatched.**  
  Mitigation: return per-edit failure metadata with edit index, path, reason,
  closest candidates where safe, and a concise recovery hint.

- **Risk: old histories with old tool calls no longer render perfectly.**  
  Mitigation: document this as an accepted breaking release behavior paired with
  the session/history rewrite.

- **Risk: cache prefix changes reduce DeepSeek cache hits immediately after the
  release.**  
  Mitigation: keep the v3 tool docs short, deterministic, and stable; verify
  cache-prefix diagnostics after implementation.

- **Risk: strict schema requirements could recreate required-null verbosity.**  
  Mitigation: design schemas around genuinely required fields only and use
  runtime validation for shape alternatives when provider strictness requires
  trade-offs.

## Migration Plan

1. Add the v3 runtime methods for `Read`, `Write`, and `Update`, reusing the
   existing safety and text mutation helpers.
2. Replace default tool registration and tool docs with v3 definitions.
3. Remove or disable model-facing registration for the v2 file tools.
4. Update prompts, UI/TUI labels, diff previews, subagent allowlists, cache
   prefix tests, and compaction assumptions.
5. Update OpenSpec canonical specs during archive.
6. Release together with the session/history storage rewrite as a breaking
   compatibility window.

Rollback is a code rollback to the prior release; no history migration is
provided for old v2 tool calls.
