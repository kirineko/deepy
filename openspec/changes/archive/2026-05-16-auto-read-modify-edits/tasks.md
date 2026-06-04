## 1. Snapshot Semantics

- [x] 1.1 Add a file-state helper that can distinguish no managed snapshot from partial, full, and stale snapshots without weakening existing checks.
- [x] 1.2 Add an internal auto-read path for existing-file `modify(old_string/new_string)` when no managed snapshot exists.
- [x] 1.3 Ensure auto-read records the same mtime, size, encoding-sensitive content basis, and full-read state needed by the existing edit path.
- [x] 1.4 Ensure stale snapshots and partial snapshots without `snippet_id` continue to be rejected rather than silently re-read.

## 2. Modify Behavior

- [x] 2.1 Route exact existing-file modify calls through the auto-read path before matching `old_string`.
- [x] 2.2 Preserve existing exact-match, loose line-ending match, uniqueness, candidate snippet, closest-match, encoding, and line-ending behavior after auto-read.
- [x] 2.3 Keep `modify(content=...)` for existing files rejected with managed edit/replacement guidance.
- [x] 2.4 Add success metadata such as `autoReadBeforeModify` for auto-read edits while keeping normal diff and path metadata.

## 3. Tool Guidance

- [x] 3.1 Update model-facing `modify` documentation to explain that exact existing-file edits can be attempted directly, while inspection reads are still useful for understanding context.
- [x] 3.2 Update function tool descriptions or schemas if needed so the model does not learn an obsolete hard requirement to call `read` before every exact edit.
- [x] 3.3 Preserve guidance that full-file replacement, stale edits, and destructive recovery must stay inside managed file tools.

## 4. Tests

- [x] 4.1 Add a focused test where `runtime.modify("file", old=..., new=...)` succeeds on an existing file without a prior `read`.
- [x] 4.2 Assert the auto-read modify result includes normal diff metadata and the auto-read marker metadata.
- [x] 4.3 Assert an already-read file changed out of band still rejects stale `modify` instead of auto-reading and applying the edit.
- [x] 4.4 Assert `modify(content=...)` against an existing file remains rejected.
- [x] 4.5 Assert partial-read behavior still requires `snippet_id` or a full read for unscoped edits.
- [x] 4.6 Update tool description/schema tests for the revised modify guidance.

## 5. Verification

- [x] 5.1 Run focused tool tests covering file-state, modify, stale edit, snippet, and tool-description behavior.
- [x] 5.2 Run the broader project test or lint subset normally used for tool changes.
- [x] 5.3 Run `openspec validate auto-read-modify-edits --type change --strict`.
