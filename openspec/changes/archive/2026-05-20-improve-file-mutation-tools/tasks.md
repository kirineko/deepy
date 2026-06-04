## 1. Contract Baseline

- [x] 1.1 Add regression tests for built-in tool registration showing only `read_file`, `edit_text`, `write_file`, and `apply_patch` are available for file operations, with `apply_patch` preferred for complex edits and old `read`/`modify` aliases absent.
- [x] 1.2 Add tests for `edit_text` that enforce declared replacement counts, including the existing `expected_occurrences` field.
- [x] 1.3 Add tests for `write_file` new-file creation, explicit existing-file replacement with overwrite intent and snapshot/hash freshness, and unsafe replacement rejection.
- [x] 1.4 Add tests for structured file mutation failures, including absent matches, duplicate matches, no-op edits, stale snapshots, unsupported targets, and unsafe argument combinations.
- [x] 1.5 Add tests for path-boundary validation and non-regular text targets before refactoring the implementation.
- [x] 1.6 Define and test the stable file mutation error-code taxonomy and result metadata contract.

## 2. Shared Mutation Engine

- [x] 2.1 Introduce a shared managed text mutation layer for path resolution, target classification, text decoding, snapshot/hash checks, diff generation, backup metadata, approval/guardrail metadata hooks, and byte writing.
- [x] 2.2 Move existing encoding and line-ending preservation behavior into the shared text file service while migrating successful former mutation behavior to `edit_text` and `write_file`.
- [x] 2.3 Add a managed mutation state object that can track snapshot ids, partial-read ranges, snippet scopes, mtime/size/hash, and perform pre-read, post-read, and final pre-commit stale checks.
- [x] 2.4 Implement path policy checks for workspace escape, symlink escape, ignored paths, and sensitive-file policy decisions.
- [x] 2.5 Implement atomic or best-effort atomic text writes using a temporary file in the target directory and rename-over-target semantics.
- [x] 2.6 Add bounded Windows retry handling for retryable rename errors such as `EPERM` and `EACCES`.
- [x] 2.7 Return structured mutation result metadata for changed files, diffs, encodings, line endings, stale reads, policy decisions, and atomic-write fallback status.
- [x] 2.8 Add the approval and guardrail adapter boundary before side-effecting mutation commits, returning `allow`, `warn`, `requires_approval`, or `deny` structured metadata without implementing interactive approval UI.

## 3. V2 File Tools

- [x] 3.1 Implement `read_file` as the model-facing read tool with full-read snapshots, partial-read snippet metadata, content hashes, and non-text read metadata that is not tracked for text mutation.
- [x] 3.2 Implement `edit_text` for exact/string edits through the shared managed text mutation engine.
- [x] 3.3 Implement `write_file` for new-file creation and explicit whole-file replacement through the shared managed text mutation engine.
- [x] 3.4 Update tool descriptions so `edit_text` is recommended for small exact edits, `write_file` for explicit whole-file writes, and `apply_patch` for structured or multi-file changes.
- [x] 3.5 Remove old `read` from model-facing registration while preserving directory/media/PDF metadata behavior through `read_file`.

## 4. Apply Patch Tool

- [x] 4.1 Define the `apply_patch` tool contract as a strict-compatible single `patch` string payload parsed by a dedicated patch parser, behind an adapter that can later support an OpenAI Agents SDK ApplyPatchTool integration.
- [x] 4.2 Implement create-file patch operations through the shared managed text mutation engine.
- [x] 4.3 Implement update-file patch operations through the shared managed text mutation engine.
- [x] 4.4 Implement delete-file patch operations through the shared managed mutation path with structured deletion metadata.
- [x] 4.5 Implement move-file patch operations with source and destination path validation and result metadata.
- [x] 4.6 Return multi-file diff metadata and patch warning/fuzz diagnostics for skipped, ambiguous, or approximate matches.
- [x] 4.7 Implement preflight validation for all patch operations before committing any file side effects.
- [x] 4.8 Report partial-commit metadata if a late platform error occurs after preflight and after one or more operations have committed.
- [x] 4.9 Accept conservative paired `@@` old-block/new-block update hunks so model-generated patches with blank lines can apply without falling back to `edit_text`.
- [x] 4.10 Render pending `apply_patch` calls with concise target paths instead of the full patch body.
- [x] 4.11 Accept common model-generated patch wrappers and headers, including Markdown fences, unified diff file headers, `a/`/`b/` prefixes, EOF newline variants, and CSS/YAML replacement-block prefixes.

## 5. Legacy Tool Removal

- [x] 5.1 Remove old `modify` from model-facing tool registration.
- [x] 5.2 Remove old `read` and `modify` tool docs from the system prompt tool documentation block.
- [x] 5.3 Migrate tests and prompt guidance from old `modify` behavior to `edit_text`, `write_file`, and `apply_patch`.
- [x] 5.4 Remove legacy `modify` schema and invocation adapter from the Agents SDK tool layer.
- [x] 5.5 Ensure no model-facing compatibility alias remains that can compete with the v2 tool names.

## 6. Windows And Encoding

- [x] 6.1 Add regression coverage that new managed text files are written as UTF-8 without BOM by default.
- [x] 6.2 Add regression coverage that existing UTF-8 with BOM, UTF-16LE, GB18030, LF, and CRLF files keep their detected encoding and line-ending style after mutation.
- [x] 6.3 Add Windows-focused tests for temporary-file rename retry behavior and fallback metadata.
- [x] 6.4 Add coverage for `.bat` and `.cmd` CRLF behavior if Deepy adopts a script-specific newline policy.
- [x] 6.5 Verify the refactor does not regress existing Windows PowerShell 7 shell-output encoding behavior.
- [x] 6.6 Keep `.ps1` new-file UTF-8 BOM behavior unchanged unless a separate decision explicitly changes the new-file encoding policy.

## 7. Agents SDK Alignment

- [x] 7.1 Make `read_file`, `edit_text`, `write_file`, and `apply_patch` schemas strict-compatible where practical, with required fields and nullable optional semantics when represented as FunctionTools.
- [x] 7.2 Remove the legacy `modify` schema from the model-facing tool surface and keep ambiguous validation in the v2 runtime paths.
- [x] 7.3 Add internal extension points for future `needs_approval` or tool guardrail integration before committing side-effecting file mutations.
- [x] 7.4 Ensure `requires_approval` returns a structured policy result without committing side effects or launching an interactive approval flow in this change.
- [x] 7.5 Update tool schema tests and prompt/tool fixture tests to reflect the new primary editing contract.

## 8. Verification

- [x] 8.1 Run targeted tool tests for file state, file mutations, tool schemas, and prompt/tool documentation.
- [x] 8.2 Run Windows/encoding regression tests or their platform-simulated equivalents.
- [x] 8.3 Run stale/TOCTOU, partial snippet, expected-occurrence, no-op, path-policy, symlink-policy, and multi-file patch regression tests.
- [x] 8.4 Run the relevant project test command for the touched tool modules.
- [x] 8.5 Run edit argument recovery regressions for null-like snippet ids and snapshot ids passed as snippet ids.
- [x] 8.6 Run `openspec validate improve-file-mutation-tools --strict`.

## 9. Usage-Driven Refinement

- [x] 9.1 Add regression coverage for `edit_text` auto-promoting a fresh partial
  read to a full-file exact edit when `file_path` is provided.
- [x] 9.2 Add regression coverage for `edit_text` recovering from an overly
  narrow snippet scope when the same exact edit matches the full file safely.
- [x] 9.3 Update prompt and tool guidance so small single-file exact edits prefer
  `edit_text`, while `apply_patch` is reserved for multi-file, delete/move, or
  large structured changes.
- [x] 9.4 Clarify `apply_patch` guidance so the model uses it for multiple edits
  in one file as well as multi-file/delete/move changes, with concrete patch
  grammar cues in the tool description.
- [x] 9.5 Compact multi-file `apply_patch` diff previews so every changed file
  gets visible preview budget while full diff metadata remains available.
- [x] 9.6 Show multi-file `apply_patch` pending calls with file counts and
  concise path summaries to reduce uncertainty during longer patch execution.
- [x] 9.7 Accept common HTML patch mistakes where blank context lines or
  unmarked context lines omit unified-diff prefixes, while still relying on
  exact patch matching before writing.
