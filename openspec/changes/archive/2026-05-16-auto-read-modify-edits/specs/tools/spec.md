## MODIFIED Requirements

### Requirement: Read-Before-Write Protection

Deepy SHALL protect existing files from stale or uninformed writes by ensuring a
managed file snapshot exists before committing existing-file changes.

#### Scenario: Existing file is exact-modified without a prior snapshot

- **WHEN** the model invokes `modify` with `old_string` and `new_string` for an
  existing file that has no managed snapshot in the current tool runtime
- **THEN** Deepy SHALL internally establish a managed snapshot from the current
  file contents before applying the edit
- **AND** Deepy SHALL apply the edit only if the existing exact-match,
  uniqueness, encoding, and line-ending checks pass
- **AND** the successful result SHALL include metadata indicating that an
  internal auto-read snapshot was used

#### Scenario: Existing file is full-content modified without a prior snapshot

- **WHEN** the model invokes `modify` with `content` for an existing file
- **THEN** Deepy SHALL reject the operation
- **AND** Deepy SHALL direct the model to use the managed existing-file edit or
  replacement flow instead

#### Scenario: Existing file changed after a managed snapshot

- **WHEN** a tool attempts to write or modify an existing file that already has a
  managed snapshot
- **AND** the file has changed since that snapshot was recorded
- **THEN** Deepy SHALL reject the operation
- **AND** it SHALL require the file to be read again before editing

### Requirement: Unified File Modification Path

Deepy SHALL prefer a unified modify/edit path for file changes so the model does
not repeatedly call write, read, and edit for the same existing file.

#### Scenario: Model changes existing code

- **WHEN** the model needs to update an existing file
- **THEN** tool descriptions SHALL steer it toward the modification tool instead
  of full-file write

#### Scenario: Model exact-edits an existing file before reading it

- **WHEN** the model invokes `modify` with `old_string` and `new_string` for an
  existing file before invoking `read`
- **THEN** Deepy SHALL complete the edit in the same tool call when the internal
  snapshot and exact edit checks succeed
- **AND** Deepy SHALL NOT require a failed modify result followed by a separate
  read call for this recoverable missing-snapshot case
