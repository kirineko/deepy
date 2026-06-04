## Context

Deepy now has a v2 file mutation surface with `read_file`, `edit_text`,
`write_file`, and `apply_patch`, plus a shared managed mutation engine for path
policy, text decoding, stale checks, diff generation, atomic writes, and
guardrail metadata. The remaining weak point is the model-facing `apply_patch`
payload: it asks the model to handwrite a custom patch string. User traces show
that this string protocol fails frequently for HTML/CSS blocks and makes
multi-file edits slow and opaque while the user waits.

This change is still pre-release, so compatibility with the patch-string
payload is not required. The implementation can replace the model-facing schema
directly while preserving the `apply_patch` tool name.

## Goals / Non-Goals

**Goals:**

- Keep the model-facing tool name `apply_patch`.
- Replace patch-string input with a strict-compatible structured
  `operations` list.
- Support create, replace-file, delete, move, block replacement, insert-before,
  insert-after, and replace-all operations.
- Route every operation through the existing managed mutation engine.
- Improve pending UI by showing operation and file summaries immediately.
- Improve result UI so multi-file changes show visible diff sections for every
  changed file within the preview budget.
- Preserve existing Windows text behavior: new files use UTF-8 without BOM,
  existing files keep detected encoding and line endings, and `.bat`/`.cmd`
  newline policy remains governed by the managed text service.

**Non-Goals:**

- No legacy `patch: string` compatibility path.
- No new model-facing tool name such as `apply_operations`.
- No broad fuzzy edit mode that silently applies approximate matches.
- No change to the `edit_text` role for small exact single-file edits.
- No new interactive approval UI.

## Decisions

### 1. Keep `apply_patch`, change its payload

The tool name remains stable because the model already needs one primary tool
for complex edits. Adding a second operation-based tool would compete with
`apply_patch` and weaken tool selection.

The payload becomes an operation list:

```json
{
  "operations": [
    {
      "type": "replace_block",
      "file_path": "portfolio/index.html",
      "old_text": "...",
      "new_text": "...",
      "expected_occurrences": 1
    }
  ]
}
```

Alternative considered: keep `patch` as a nullable fallback field. That would
reduce short-term migration risk, but this protocol has not shipped yet and the
fallback would keep teaching models to use the fragile path.

### 2. Use a strict-compatible operation object

OpenAI Agents SDK strict schemas work best with required fields and nullable
optional semantics. The operation schema should therefore use a single
operation object with a `type` discriminator and nullable fields, with runtime
validation enforcing the field set for each operation type.

This avoids relying on complex JSON Schema union behavior while still producing
clear structured validation errors.

### 3. Normalize operations before planning mutations

`apply_patch` should parse and validate model input into an internal
`FileMutationOperation` list, then group operations by affected file and build a
single preflight plan. No operation should write until all operations have
passed path, text, snapshot, matching, parent-directory, backup, and guardrail
checks.

This keeps the all-or-preflight behavior users expect from a patch-oriented
tool while still preserving partial-commit metadata for late platform errors.

### 4. Make matching conservative and explicit

`replace_block`, `insert_before`, `insert_after`, and `replace_all` use exact
text matching with line-ending normalization through the existing text service.
`expected_occurrences` is enforced when provided and defaults to one for anchor
and block operations. Approximate candidates may be returned as diagnostics,
but they must not be applied silently.

This keeps retries deterministic and avoids replacing parser failures with
unsafe fuzzy behavior.

### 5. Treat UI summary as part of the protocol

Structured input gives Deepy enough information to summarize a pending call
before execution:

- operation count
- target file count
- concise target file names
- destructive operation markers for delete or move

Result metadata should include per-file summaries and per-file diff preview
sections, so the UI never shows only one changed file for a multi-file patch.

## Risks / Trade-offs

- **Risk: Strict schema becomes verbose** -> Use one operation shape with
  nullable fields and clear runtime validation by operation type.
- **Risk: Models overuse `apply_patch` for tiny edits** -> Keep prompt guidance
  that `edit_text` is preferred for one small exact single-file edit.
- **Risk: Large `replace_file` operations still create long tool arguments** ->
  Keep UI pending summaries independent of raw arguments and rely on result
  diff previews rather than rendering full content.
- **Risk: Batch preflight blocks simple partial progress** -> Preserve atomic
  multi-file semantics by default; surface per-operation diagnostics when
  preflight rejects the batch.
- **Risk: Removing the patch-string parser breaks local habits before release**
  -> This is acceptable because the file tool surface has not shipped; tests
  and prompts should be updated together in this change.

## Migration Plan

1. Replace the `apply_patch` schema and tool documentation with the structured
   `operations` contract.
2. Remove the patch-string parser from the model-facing execution path.
3. Implement operation validation and normalization into the existing mutation
   planning objects.
4. Reuse the managed mutation engine for all operation types.
5. Update pending and result display code to summarize structured operations.
6. Update prompt fixtures, schema tests, tool tests, and UI tests.
7. Run OpenSpec validation plus targeted mutation, encoding, and display tests.
