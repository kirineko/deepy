## MODIFIED Requirements

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
