## ADDED Requirements

### Requirement: Structured Apply Patch Protocol

Deepy SHALL define `apply_patch` as a structured operation-list protocol for
complex file mutations.

#### Scenario: Structured operations are accepted

- **WHEN** the model invokes `apply_patch`
- **THEN** the tool input SHALL contain an `operations` list
- **AND** each item SHALL declare a supported operation `type`
- **AND** Deepy SHALL validate the required and forbidden fields for that
  operation type before planning file side effects

#### Scenario: Patch string input is not accepted

- **WHEN** the model invokes `apply_patch` with a patch-string payload instead
  of structured operations
- **THEN** Deepy SHALL reject the call as invalid tool input
- **AND** the recovery hint SHALL direct the model to use structured
  `operations`

### Requirement: Apply Patch Operation Types

Deepy SHALL support explicit operation types for file creation, whole-file
replacement, deletion, movement, block replacement, anchored insertion, and
exact replace-all changes.

#### Scenario: File is created

- **WHEN** an operation has `type` set to `create_file`
- **THEN** Deepy SHALL require `file_path` and `content`
- **AND** it SHALL create the target only when the target does not already exist
  unless the operation explicitly allows overwrite through a supported
  validation path
- **AND** the created text file SHALL use UTF-8 without BOM by default

#### Scenario: File is replaced

- **WHEN** an operation has `type` set to `replace_file`
- **THEN** Deepy SHALL require `file_path`, `content`, explicit overwrite
  intent, and a freshness token such as a snapshot id or expected hash
- **AND** it SHALL preserve the existing file's detected encoding and
  line-ending style unless an allowed encoding change is explicitly requested

#### Scenario: File is deleted

- **WHEN** an operation has `type` set to `delete_file`
- **THEN** Deepy SHALL require `file_path`
- **AND** it SHALL validate path policy, target type, backup policy, and
  guardrail policy before deleting the file

#### Scenario: File is moved

- **WHEN** an operation has `type` set to `move_file`
- **THEN** Deepy SHALL require `file_path` and `destination_path`
- **AND** it SHALL validate both source and destination through the path policy
  layer before committing the move

#### Scenario: Block is replaced

- **WHEN** an operation has `type` set to `replace_block`
- **THEN** Deepy SHALL require `file_path`, `old_text`, and `new_text`
- **AND** it SHALL replace only exact matches that satisfy
  `expected_occurrences`

#### Scenario: Content is inserted around an anchor

- **WHEN** an operation has `type` set to `insert_before` or `insert_after`
- **THEN** Deepy SHALL require `file_path`, `anchor`, and `content`
- **AND** it SHALL insert relative to exact anchor matches that satisfy
  `expected_occurrences`

#### Scenario: All exact matches are replaced

- **WHEN** an operation has `type` set to `replace_all`
- **THEN** Deepy SHALL require `file_path`, `old_text`, and `new_text`
- **AND** it SHALL replace every exact match in the target file
- **AND** it SHALL reject the operation when no match exists

### Requirement: Structured Patch Preflight

Deepy SHALL plan all structured patch operations before committing any file side
effects.

#### Scenario: Operation batch preflight succeeds

- **WHEN** all operations pass schema validation, path policy, target
  classification, text decoding, snapshot freshness, matching, parent-directory
  planning, backup planning, and guardrail checks
- **THEN** Deepy SHALL commit the planned mutations through the managed mutation
  engine
- **AND** it SHALL return per-operation and per-file result metadata

#### Scenario: Operation batch preflight fails

- **WHEN** any operation fails validation or preflight
- **THEN** Deepy SHALL reject the entire batch before committing file side
  effects
- **AND** the result SHALL identify every reportable failed operation with a
  stable error code and recovery hint

#### Scenario: Matching diagnostics are available

- **WHEN** a text operation cannot find an exact match or finds an ambiguous
  match count
- **THEN** Deepy SHALL return structured diagnostics such as expected count,
  actual count, closest candidates, or anchor context when safe to expose
- **AND** it SHALL NOT apply approximate matches silently

### Requirement: Structured Patch Result Metadata

Deepy SHALL return structured metadata for operation batches and changed files.

#### Scenario: Structured patch succeeds

- **WHEN** `apply_patch` commits one or more structured operations
- **THEN** the result metadata SHALL include the operation count, changed file
  count, changed file paths, operation summaries, encoding and line-ending
  decisions, and diff metadata
- **AND** `diff_preview` SHALL contain the full patch diff rather than a compact
  or truncated preview

#### Scenario: Late platform failure occurs

- **WHEN** a late platform error occurs after preflight and after one or more
  operations have committed
- **THEN** Deepy SHALL return partial-commit metadata identifying committed
  operations, failed operations, affected files, and available backup or
  recovery metadata
