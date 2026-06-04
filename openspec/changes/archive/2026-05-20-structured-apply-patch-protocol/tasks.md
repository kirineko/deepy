## 1. Schema And Prompt Contract

- [x] 1.1 Replace the model-facing `apply_patch` schema with a strict-compatible `operations` list and remove the patch-string field from registration.
- [x] 1.2 Define operation validation rules for `create_file`, `replace_file`, `delete_file`, `move_file`, `replace_block`, `insert_before`, `insert_after`, and `replace_all`.
- [x] 1.3 Update `apply_patch` tool docs to show concise structured operation examples and remove Codex-style patch string instructions.
- [x] 1.4 Update system prompt/tool guidance so small exact single-file edits prefer `edit_text`, and multi-edit or multi-file work prefers structured `apply_patch`.
- [x] 1.5 Update schema and prompt fixture tests so no model-facing patch-string contract remains.

## 2. Operation Planning

- [x] 2.1 Add internal structured operation models and normalize incoming tool arguments into a common mutation plan.
- [x] 2.2 Implement operation-specific required-field, forbidden-field, and no-op validation with stable error codes and recovery hints.
- [x] 2.3 Group operations by affected file while preserving user-provided order for sequential edits within the same file.
- [x] 2.4 Implement all-operation preflight so validation, path policy, text decoding, snapshot freshness, match planning, parent-directory planning, backup planning, and guardrail checks complete before any file side effect.
- [x] 2.5 Preserve partial-commit metadata for late platform failures after successful preflight.

## 3. Operation Execution

- [x] 3.1 Implement `create_file` through the managed text mutation path with UTF-8 without BOM defaults.
- [x] 3.2 Implement `replace_file` through the managed text mutation path with explicit overwrite intent and freshness-token enforcement.
- [x] 3.3 Implement `delete_file` and `move_file` through the managed mutation path with path-policy, backup, and guardrail metadata.
- [x] 3.4 Implement `replace_block` with exact matching, line-ending normalization, `expected_occurrences`, and structured absent/ambiguous diagnostics.
- [x] 3.5 Implement `insert_before` and `insert_after` with exact anchor matching, `expected_occurrences`, and structured absent/ambiguous diagnostics.
- [x] 3.6 Implement `replace_all` with actual replacement-count metadata and rejection when no match exists.
- [x] 3.7 Remove or isolate the old patch-string parser so it is no longer reachable from the model-facing `apply_patch` path.

## 4. UI And Result Metadata

- [x] 4.1 Update pending `apply_patch` rendering to summarize operation count, file count, and concise target file names from structured operations.
- [x] 4.2 Ensure pending rendering never displays full file contents, replacement blocks, anchors, or raw operation JSON.
- [x] 4.3 Update successful result metadata to include operation count, changed file count, changed files, per-operation summaries, encoding and line-ending decisions, and full diff metadata.
- [x] 4.4 Update multi-file diff preview rendering so every changed file receives visible preview budget.
- [x] 4.5 Add UI/TUI regression coverage for single-file, multi-file, destructive, and large-content structured patch summaries.
- [x] 4.6 Render full `apply_patch` diffs without compacting, while listing every target path in pending argument summaries.
- [x] 4.7 Render multi-file `apply_patch` diffs as separate per-file sections so each file receives its own syntax highlighting.

## 5. Windows And Encoding Regression

- [x] 5.1 Verify structured `create_file` keeps the Deepy policy of UTF-8 without BOM for new text files on all platforms.
- [x] 5.2 Verify structured updates preserve existing UTF-8-sig, UTF-16LE, UTF-8, GB18030, LF, and CRLF metadata.
- [x] 5.3 Verify `.bat` and `.cmd` newline behavior remains governed by the managed text file service.
- [x] 5.4 Verify no `.ps1` automatic BOM behavior is introduced by the structured protocol.
- [x] 5.5 Verify stale/TOCTOU checks still reject changed files before structured operations commit.

## 6. Verification

- [x] 6.1 Add targeted unit tests for each structured operation type and validation failure mode.
- [x] 6.2 Add integration tests for multi-file all-preflight success, preflight rejection with no side effects, and late partial-commit metadata.
- [x] 6.3 Run the file mutation, prompt/tool docs, message view, and TUI diff test suites affected by the schema change.
- [x] 6.4 Run `ruff`, `ty`, and the relevant project test command for touched modules.
- [x] 6.5 Run `openspec validate structured-apply-patch-protocol --strict`.
