# file-tools-v3 Specification

## Purpose
TBD - created by archiving change rewrite-file-tools-read-write-update. Update Purpose after archive.
## Requirements
### Requirement: V3 File Tool Surface
Deepy SHALL expose a breaking v3 model-facing file tool surface consisting of
`Read`, `Write`, and `Update`.

#### Scenario: V3 file tools are registered
- **WHEN** Deepy constructs the main model agent for a new run
- **THEN** it SHALL register `Read`, `Write`, and `Update` through the OpenAI
  Agents SDK tool flow
- **AND** it SHALL NOT register `read_file`, `edit_text`, `write_file`, or
  `apply_patch` as model-facing built-in file tools
- **AND** the v3 tool descriptions SHALL use short, direct guidance that maps
  reading, whole-file writing, and exact text updates to the three tools

#### Scenario: Old file tools are unsupported
- **WHEN** old session/history content or a model attempts to invoke
  `read_file`, `edit_text`, `write_file`, or `apply_patch` after the v3 file
  tool release
- **THEN** Deepy SHALL NOT provide an execution compatibility path for that old
  file-tool call
- **AND** old-history rendering compatibility SHALL NOT be required for those
  file-tool payloads

### Requirement: Read Tool
Deepy SHALL expose `Read` for reading one or more files, directories, or
supported descriptive non-text targets while recording runtime-managed read
state for later mutations.

#### Scenario: Single text file is read
- **WHEN** the model invokes `Read` with a text file path
- **THEN** Deepy SHALL return readable line-numbered content and metadata
- **AND** the metadata SHALL include target path, line range, total line count,
  truncation state, encoding, line-ending style, and whether the runtime recorded
  mutation-readable state for that target

#### Scenario: Multiple files are read in one call
- **WHEN** the model invokes `Read` with multiple read targets
- **THEN** Deepy SHALL resolve and read independent targets concurrently where
  the runtime permits it
- **AND** the result SHALL include per-target output, per-target metadata, and a
  concise aggregate summary
- **AND** one failed target SHALL be reported for that target without preventing
  successful read results for unrelated targets from being returned

#### Scenario: Partial file range is read
- **WHEN** the model invokes `Read` with range, offset/limit, head, or tail
  controls for a text file
- **THEN** Deepy SHALL return the requested bounded content and total line count
- **AND** it SHALL record enough runtime-managed read state for later exact
  `Update` operations while still detecting stale target changes before writing

#### Scenario: Directory or non-text target is read
- **WHEN** the model invokes `Read` for a directory or supported descriptive
  non-text target
- **THEN** Deepy SHALL return directory or descriptive metadata when supported
- **AND** it SHALL NOT mark unsupported non-text content as safely text-mutable

### Requirement: Write Tool
Deepy SHALL expose `Write` for creating new text files and explicit whole-file
replacement without exposing freshness tokens to the model.

#### Scenario: Existing file replacement is fresh
- **WHEN** the model invokes `Write` for an existing text file with explicit
  overwrite intent
- **AND** Deepy has fresh runtime-managed read state for that file or can safely
  auto-read the current file because no stale snapshot exists
- **THEN** Deepy SHALL replace the whole file through the managed text mutation
  path
- **AND** it SHALL preserve the existing file's detected encoding and
  line-ending style unless a future explicit encoding option allows otherwise

#### Scenario: Existing file replacement is stale
- **WHEN** the model invokes `Write` for an existing file after Deepy has a
  runtime-managed read state that is no longer fresh
- **THEN** Deepy SHALL reject the mutation before writing
- **AND** the result SHALL instruct the model to call `Read` for the target path
  before retrying
- **AND** the tool schema SHALL NOT require the model to pass `snapshot_id`,
  `snapshot_token`, or `expected_hash`

### Requirement: Update Tool

Deepy's v3 `Update` tool SHALL apply exact text replacements to existing text
files with simple single-file, multi-edit, and multi-file shapes.

#### Scenario: Multiple edits in one file succeed
- **WHEN** the model invokes `Update` with multiple ordered edits for the same
  file
- **THEN** Deepy SHALL apply the edits in array order to a staged copy of the
  file content
- **AND** a later edit MAY match text inserted by an earlier edit in the same
  tool call
- **AND** Deepy SHALL write the file only after all blocking edits for the call
  pass validation
- **AND** no-op edits SHALL be skipped and reported when other edits in the call
  produce file changes

#### Scenario: Multiple files are updated in one call
- **WHEN** the model invokes `Update` with edits that target more than one file
- **THEN** Deepy SHALL validate every target and blocking edit before committing
  any file side effect
- **AND** the result SHALL report the number of requested edits, applied edits,
  skipped no-op edits, changed files, changed file paths, and per-file diff
  metadata

#### Scenario: Exact edit validation fails
- **WHEN** any `Update` edit has an empty `old`, absent match, ambiguous match,
  expected-count mismatch, stale target, unsupported target, path-policy failure,
  or guardrail failure
- **THEN** Deepy SHALL reject the entire `Update` call before committing file
  side effects
- **AND** the result SHALL identify the failing edit index, target path, stable
  error code, and concise recovery hint when safe to expose

#### Scenario: Mixed no-op and valid edits are submitted
- **WHEN** an `Update` call contains at least one no-op edit and at least one edit
  that changes staged file content
- **THEN** Deepy SHALL commit the valid staged changes
- **AND** it SHALL report the no-op edits as skipped edits
- **AND** it SHALL NOT treat skipped no-op edits as preflight failures

#### Scenario: All submitted edits are no-ops
- **WHEN** every valid `Update` edit would leave file content unchanged
- **THEN** Deepy SHALL return a successful no-op result without writing files
- **AND** it SHALL report `changedFileCount=0`, `appliedEditCount=0`,
  `skippedEditCount`, `skippedEdits`, and `noOp=true`

#### Scenario: Replace all is guarded
- **WHEN** the model invokes `Update` with `replace_all=true`
- **THEN** Deepy SHALL replace every exact `old` match in the target scope
- **AND** it SHALL report the actual occurrence count
- **AND** if `expected_occurrences` is provided, Deepy SHALL reject the update
  when the actual count differs

### Requirement: V3 File Tool Schema Simplicity
Deepy's v3 file tool schemas SHALL minimize model-facing argument burden.

#### Scenario: Freshness fields are hidden
- **WHEN** Deepy exposes `Read`, `Write`, or `Update` schemas to the model
- **THEN** those schemas SHALL NOT include `snapshot_id`, `snapshot_token`,
  `expected_hash`, `snippet_id`, `old_text`, `new_text`, `old_string`, or
  `new_string` as required model-facing fields

#### Scenario: Nullable required fields are avoided
- **WHEN** Deepy exposes v3 file tool schemas to a provider
- **THEN** the schema SHALL require only fields that must be supplied for the
  selected tool shape
- **AND** Deepy SHALL avoid required nullable filler fields whose only purpose is
  satisfying an unrelated operation variant

### Requirement: V3 File Tool Result Metadata

Deepy's v3 file tools SHALL return structured metadata that supports rendering,
debugging, and cache-safe context management.

#### Scenario: Mutation succeeds
- **WHEN** `Write` or `Update` changes one or more text files
- **THEN** the result metadata SHALL include changed file paths, diff metadata,
  encoding and line-ending decisions, mutation policy metadata, refreshed
  runtime-managed read state, applied edit count, and skipped no-op edit metadata
  when applicable
- **AND** UI renderers SHALL be able to display a concise changed-file summary
  and a readable diff preview from the result

#### Scenario: Mutation fails before writing
- **WHEN** `Write` or `Update` rejects a mutation before committing file side
  effects
- **THEN** the result metadata SHALL distinguish argument errors, stale/unread
  target errors, path policy errors, unsupported target errors, match errors,
  count errors, blocking no-op-only results, and guardrail errors
- **AND** retryable argument failures SHALL remain distinguishable from blocking
  mutation safety failures

### Requirement: Read Range Argument Recovery
Deepy's v3 `Read` tool SHALL recover from common malformed line-range arguments
only when they can be safely normalized to the canonical schema shape.

#### Scenario: Single read recovers unquoted line range
- **WHEN** the model invokes `Read` with JSON-like arguments containing a target
  path and an unquoted simple inclusive line range such as `range: 80-120`
- **THEN** Deepy SHALL normalize the range to the schema-valid string form
  `"80-120"` before executing the read
- **AND** it SHALL return the requested bounded line-numbered content
- **AND** the result metadata SHALL indicate that argument repair was applied

#### Scenario: Batch read recovers unquoted target ranges
- **WHEN** the model invokes `Read` with multiple file targets and one or more
  targets contain an unquoted simple inclusive line range
- **THEN** Deepy SHALL normalize those target ranges to schema-valid string
  values before executing the batch read
- **AND** it SHALL preserve the existing per-target success and failure behavior
  for the batch result

#### Scenario: Unsafe malformed range remains retryable
- **WHEN** the model invokes `Read` with malformed arguments that cannot be
  safely normalized to the canonical schema
- **THEN** Deepy SHALL return a retryable invalid-argument result
- **AND** it SHALL NOT execute the read
- **AND** the recovery guidance SHALL continue to instruct the model to pass a
  valid JSON object matching the tool schema

### Requirement: Read Range Tool Guidance
Deepy's model-facing `Read` tool guidance SHALL make the canonical line-range
argument shape explicit.

#### Scenario: Read description shows quoted range examples
- **WHEN** Deepy exposes the v3 `Read` tool to a model
- **THEN** the tool description SHALL show that `range` values are quoted
  strings such as `"80-120"`
- **AND** the guidance SHALL cover both single-target reads and multi-target
  `files` reads

### Requirement: V3 File Mutation Preflight
Deepy's v3 file mutation tools SHALL expose an internal preflight planning path
that predicts the mutation diff without committing side effects.

#### Scenario: Write preflight matches actual write diff
- **WHEN** Deepy preflights a valid `Write` mutation
- **THEN** the preflight result SHALL include the same unified diff that the
  approved `Write` tool execution would report for the same file state
- **AND** the preflight SHALL NOT write or create the target file

#### Scenario: Update preflight matches actual update diff
- **WHEN** Deepy preflights a valid `Update` mutation
- **THEN** the preflight result SHALL include the same unified diff that the
  approved `Update` tool execution would report for the same file state
- **AND** the preflight SHALL NOT write the target files

#### Scenario: Preflight preserves mutation guardrails
- **WHEN** a `Write` or `Update` mutation would fail path policy, stale snapshot,
  unsupported target, invalid argument, or exact-match validation
- **THEN** the preflight result SHALL report the blocking error
- **AND** it SHALL NOT provide an approval path that bypasses the guardrail

