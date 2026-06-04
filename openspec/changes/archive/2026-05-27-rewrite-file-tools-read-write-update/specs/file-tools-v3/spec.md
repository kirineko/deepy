## ADDED Requirements

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

#### Scenario: New file is written
- **WHEN** the model invokes `Write` for a path that does not exist
- **THEN** Deepy SHALL create parent directories as needed within the mutation
  policy boundary
- **AND** it SHALL write the provided content through the managed text mutation
  path
- **AND** it SHALL record runtime-managed read state for the written content

#### Scenario: Existing file replacement is fresh
- **WHEN** the model invokes `Write` for an existing text file with explicit
  overwrite intent
- **AND** Deepy has fresh runtime-managed read state for that file
- **THEN** Deepy SHALL replace the whole file through the managed text mutation
  path
- **AND** it SHALL preserve the existing file's detected encoding and
  line-ending style unless a future explicit encoding option allows otherwise

#### Scenario: Existing file replacement is stale or unread
- **WHEN** the model invokes `Write` for an existing file without fresh
  runtime-managed read state
- **THEN** Deepy SHALL reject the mutation before writing
- **AND** the result SHALL instruct the model to call `Read` for the target path
  before retrying
- **AND** the tool schema SHALL NOT require the model to pass `snapshot_id`,
  `snapshot_token`, or `expected_hash`

### Requirement: Update Tool
Deepy SHALL expose `Update` for exact text replacement edits across one or more
files in one tool call.

#### Scenario: Single exact edit succeeds
- **WHEN** the model invokes `Update` with a target path, `old`, and `new`
- **AND** the target is a supported text file within the mutation boundary
- **AND** the target has fresh runtime-managed read state or can be safely
  auto-read according to the current mutation policy
- **THEN** Deepy SHALL replace the exact matching text through the managed text
  mutation path
- **AND** it SHALL preserve the target file's detected encoding and line-ending
  style

#### Scenario: Multiple edits in one file succeed
- **WHEN** the model invokes `Update` with multiple ordered edits for the same
  file
- **THEN** Deepy SHALL apply the edits in array order to a staged copy of the
  file content
- **AND** a later edit MAY match text inserted by an earlier edit in the same
  tool call
- **AND** Deepy SHALL write the file only after all edits for the call pass
  validation

#### Scenario: Multiple files are updated in one call
- **WHEN** the model invokes `Update` with edits that target more than one file
- **THEN** Deepy SHALL validate every target and edit before committing any file
  side effect
- **AND** the result SHALL report the number of edits, changed files, changed
  file paths, and per-file diff metadata

#### Scenario: Exact edit validation fails
- **WHEN** any `Update` edit has an empty `old`, absent match, ambiguous match,
  expected-count mismatch, no-op replacement, stale target, unsupported target,
  path-policy failure, or guardrail failure
- **THEN** Deepy SHALL reject the entire `Update` call before committing file
  side effects
- **AND** the result SHALL identify the failing edit index, target path, stable
  error code, and concise recovery hint when safe to expose

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
  encoding and line-ending decisions, mutation policy metadata, and refreshed
  runtime-managed read state
- **AND** UI renderers SHALL be able to display a concise changed-file summary
  and a readable diff preview from the result

#### Scenario: Mutation fails before writing
- **WHEN** `Write` or `Update` rejects a mutation before committing file side
  effects
- **THEN** the result metadata SHALL distinguish argument errors, stale/unread
  target errors, path policy errors, unsupported target errors, match errors,
  count errors, no-op edits, and guardrail errors
- **AND** retryable argument failures SHALL remain distinguishable from blocking
  mutation safety failures
