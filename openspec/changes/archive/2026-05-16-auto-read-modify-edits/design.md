## Context

Deepy's file safety model is built around managed snapshots. `read` records file
mtime, size, and whether the full file was read; `modify` delegates existing-file
changes to the edit path, which rejects files that do not have an acceptable
snapshot. That protects against stale or uninformed writes, but it also creates a
poor common-path interaction: a model may already know the exact `old_string`
from surrounding context, call `modify`, receive a visible "read before" failure,
then call `read` and repeat the same `modify`.

This change keeps the safety model but moves the first missing-snapshot recovery
inside the managed modify tool for exact replacements.

## Goals / Non-Goals

**Goals:**

- Reduce the common existing-file exact edit flow from `modify` failure, `read`,
  `modify` to one successful `modify` call.
- Avoid showing users a failed tool result for the recoverable missing-snapshot
  case.
- Preserve stale-write protection once Deepy has observed a file snapshot.
- Preserve the distinction between exact edits and full-file overwrites.
- Make the behavior visible to tests and machine consumers through metadata.

**Non-Goals:**

- Do not allow `modify(content=...)` to overwrite existing files without a prior
  managed read/write flow.
- Do not automatically recover stale snapshots by silently re-reading a file that
  changed after Deepy observed it.
- Do not change terminal rendering just to hide failed tool results.
- Do not alter public tool names or add a new tool.

## Decisions

1. Auto-read only when no managed snapshot exists.

   When an existing-file `modify(old_string/new_string)` reaches the edit path
   and the file has no `FileState` snapshot, Deepy should read current file
   metadata and content internally before matching `old_string`. The snapshot is
   therefore based on the exact bytes Deepy is about to edit.

   Alternative considered: relax `check_writable(require_read=True)` globally.
   That would make unrelated write paths less explicit and could weaken
   existing-file overwrite protection.

2. Keep stale snapshots stale.

   If a file already has a full or partial snapshot and `check_writable` reports
   that it changed since it was read, Deepy should keep rejecting the edit and ask
   the model to re-read. Auto-read is only a recovery for "not seen yet", not for
   "seen and changed".

   Alternative considered: auto-read on every stale edit and retry. That would
   hide concurrent user edits from the model and could apply an old replacement
   assumption to newer content.

3. Preserve full-file overwrite safety.

   `modify(content=...)` should continue to create new files only. Existing files
   should still require the managed read/write replacement path so Deepy can
   preserve encoding, line endings, and stale-delete safeguards.

   Alternative considered: allow `content` to replace existing files after an
   internal read. That solves a different workflow and increases blast radius.

4. Represent auto-read as metadata, not as a second visible tool event.

   A successful auto-read modify should include metadata such as
   `autoReadBeforeModify: true` and continue returning normal diff metadata. The
   UI does not need a separate `[Read]` entry or a warning, because the internal
   read is an implementation detail of a successful managed edit.

   Alternative considered: emit a synthetic read event before the modify result.
   That would preserve observability but would also keep the user-visible tool
   noise this change is intended to reduce.

5. Keep snippet semantics explicit.

   If a `snippet_id` is provided, the existing snippet-scoped edit path should
   remain unchanged. If only a partial snapshot exists and the model does not
   provide a snippet, Deepy should not treat that as a clean no-snapshot case;
   it should continue requiring a full read or a snippet-scoped edit.

   Alternative considered: auto-upgrade partial snapshots to full snapshots.
   That is feasible later, but it changes partial-read semantics and is not
   necessary to solve the observed missing-read failure.

## Risks / Trade-offs

- Exact replacements can still fail after the internal read if `old_string` is
  absent or non-unique -> keep existing closest-match, candidate snippet, and
  repeated-match metadata.
- Auto-read may read large files that the model did not explicitly request ->
  apply the behavior only on exact edit attempts and keep existing read/modify
  size and decoding constraints intact.
- Metadata naming could drift from UI expectations -> add focused tests for the
  JSON shape and keep terminal output based on the normal successful modify
  result.
- Prompt guidance may still tell the model to read first -> update tool docs and
  descriptions to make explicit read optional for exact existing-file modify
  while preserving guidance for inspection and risky edits.
