## MODIFIED Requirements

### Requirement: Unified File Modification Path

Deepy SHALL prefer a structured operation-based patch path for related file
changes so the model does not repeatedly call write, read, and edit for related
updates.

#### Scenario: Model changes existing code

- **WHEN** the model needs to update existing code, tests, docs, or config
- **THEN** tool descriptions SHALL steer it toward `edit_text` for one small
  single-file exact replacement or insertion
- **AND** tool descriptions SHALL steer it toward `apply_patch` when the change
  has multiple edits in one file, touches multiple files, deletes or moves files,
  creates files as part of a broader change, or replaces a larger block
- **AND** the `apply_patch` description SHALL describe structured `operations`
  rather than a handwritten patch string DSL

#### Scenario: Model exact-edits an existing file before reading it

- **WHEN** the model invokes `edit_text` with `old_string` and `new_string` for
  an existing file before invoking `read_file`
- **THEN** Deepy SHALL complete the edit in the same tool call when the internal
  snapshot and exact edit checks succeed
- **AND** Deepy SHALL NOT require a failed edit result followed by a separate
  read call for this recoverable missing-snapshot case

#### Scenario: Model exact-edits after a partial read

- **WHEN** the model has only partially read an existing file
- **AND** it invokes `edit_text` with a `file_path` for a normal single-file
  exact edit
- **THEN** Deepy SHALL NOT require a failed edit result followed by a separate
  full-file read when the current file is fresh and the exact edit checks pass
- **AND** Deepy SHALL still reject stale partial snapshots before writing

#### Scenario: Model performs a multi-file edit

- **WHEN** the model needs to create, update, delete, or move multiple files as
  one logical change
- **THEN** Deepy's tool guidance SHALL steer the model toward `apply_patch`
- **AND** successful results SHALL identify every changed file in structured
  metadata

### Requirement: Tool Output Display

Deepy SHALL render tool activity as concise progress and readable diffs for
managed file mutations.

#### Scenario: File content changes

- **WHEN** `write_file`, `edit_text`, or `apply_patch` succeeds
- **THEN** Deepy SHALL render a diff-style preview of changed content
- **AND** additions and deletions SHALL be visually distinguishable without
  relying only on leading `+` or `-` markers

#### Scenario: Patch changes multiple files

- **WHEN** `apply_patch` succeeds for multiple file operations
- **THEN** Deepy SHALL render a concise changed-file summary
- **AND** its display diff preview SHALL include the full diff for every changed
  file without compacting or truncating the patch diff preview
- **AND** multi-file patch diffs SHALL be rendered as separate per-file sections
  so each section can use its own file path for syntax highlighting
- **AND** detailed full diff metadata SHALL remain available for UI renderers

#### Scenario: Structured patch call arguments are summarized

- **WHEN** Deepy renders a pending `apply_patch` tool call with structured
  operations
- **THEN** it SHALL summarize the call with the operation count, number of target
  files, and all concise target file paths
- **AND** it SHALL NOT render full file contents, replacement blocks, anchors, or
  raw operation JSON as the tool-call argument summary

### Requirement: Apply Patch Primary Editing Tool

Deepy SHALL expose `apply_patch` as the primary model-facing tool for structured
file mutations.

#### Scenario: Apply patch tool is registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL register an `apply_patch` tool through the OpenAI Agents SDK
  tool flow
- **AND** the tool description SHALL identify it as the preferred tool for
  multi-file and structured file edits
- **AND** the tool schema SHALL expose a structured `operations` list instead of
  a patch-string payload

#### Scenario: Patch creates a file

- **WHEN** the model invokes `apply_patch` with a `create_file` operation
- **AND** the target path does not exist
- **THEN** Deepy SHALL create the file through the managed text mutation path
- **AND** the new file SHALL use UTF-8 without BOM by default

#### Scenario: Patch replaces a file

- **WHEN** the model invokes `apply_patch` with a `replace_file` operation
- **AND** the target file is a supported text file
- **THEN** Deepy SHALL replace the file through the managed text mutation path
- **AND** it SHALL require explicit overwrite intent and a freshness token for
  existing-file replacement
- **AND** it SHALL preserve the target file's detected encoding and line-ending
  style

#### Scenario: Patch replaces a block

- **WHEN** the model invokes `apply_patch` with a `replace_block` operation
- **AND** the target file is a supported text file
- **AND** the `old_text` matches exactly and satisfies `expected_occurrences`
- **THEN** Deepy SHALL replace the matching text with `new_text` through the
  managed text mutation path
- **AND** absent, ambiguous, or unexpected match counts SHALL be reported through
  structured failure metadata

#### Scenario: Patch inserts content around an anchor

- **WHEN** the model invokes `apply_patch` with an `insert_before` or
  `insert_after` operation
- **AND** the target file is a supported text file
- **AND** the `anchor` matches exactly and satisfies `expected_occurrences`
- **THEN** Deepy SHALL insert the requested content through the managed text
  mutation path
- **AND** absent, ambiguous, or unexpected anchor counts SHALL be reported
  through structured failure metadata

#### Scenario: Patch replaces all exact matches

- **WHEN** the model invokes `apply_patch` with a `replace_all` operation
- **AND** the target file is a supported text file
- **THEN** Deepy SHALL replace every exact `old_text` match with `new_text`
- **AND** the result SHALL include the actual replacement count

#### Scenario: Patch preflight fails

- **WHEN** the model invokes `apply_patch`
- **AND** any operation fails schema validation, path policy, target
  classification, snapshot freshness, text matching, parent-directory planning,
  backup planning, or guardrail planning
- **THEN** Deepy SHALL reject the patch before committing any file side effects
- **AND** the result SHALL identify every failed operation that can be reported
  safely

#### Scenario: Patch deletes a file

- **WHEN** the model invokes `apply_patch` with a `delete_file` operation
- **AND** the target file is within the allowed file-mutation boundary
- **THEN** Deepy SHALL delete the file through the managed mutation path
- **AND** the result SHALL include structured metadata identifying the deletion

#### Scenario: Patch moves a file

- **WHEN** the model invokes `apply_patch` with a `move_file` operation
- **AND** the source and destination are within the allowed file-mutation
  boundary
- **THEN** Deepy SHALL apply the move through the managed mutation path
- **AND** it SHALL include both source and destination paths in result metadata

#### Scenario: Patch commit partially fails

- **WHEN** a late platform error occurs after patch preflight succeeds and after
  one or more operations have committed
- **THEN** Deepy SHALL return a structured partial-commit error
- **AND** the result metadata SHALL identify committed operations, failed
  operations, and available backup or recovery metadata
