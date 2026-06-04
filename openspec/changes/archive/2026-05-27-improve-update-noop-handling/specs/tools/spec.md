## MODIFIED Requirements

### Requirement: Structured File Mutation Errors

Deepy SHALL return structured error metadata for built-in file mutation failures.

#### Scenario: Mutation has no effect
- **WHEN** a built-in text mutation would produce the same bytes as the current
  file
- **THEN** Deepy SHALL return a structured no-op result according to the tool
  contract
- **AND** it SHALL NOT silently report a successful content change
- **AND** for mixed `Update` batches it SHALL report no-op edits as skipped while
  allowing other valid staged edits to commit

### Requirement: Retryable Tool Failure Metadata

Deepy SHALL distinguish recoverable argument failures from unrecoverable tool
failures through structured metadata.

#### Scenario: Safety failures remain blocking
- **WHEN** a file mutation fails because of stale snapshots, missing freshness
  tokens for existing-file replacement, path policy, unsupported target type,
  approval policy, guardrails, absent matches, ambiguous matches, count
  mismatches, atomic write failure, backup failure, or partial commit
- **THEN** Deepy SHALL NOT mark the result as a repaired argument success
- **AND** it SHALL preserve the existing blocking failure semantics and metadata
  for that error class

## ADDED Requirements

### Requirement: Tool Progress Failure Details

Deepy SHALL surface the first structured tool preflight failure in concise
progress summaries.

#### Scenario: Update preflight fails with structured failures
- **WHEN** `Update` returns a preflight failure with `metadata.failures`
- **THEN** Deepy SHALL include the first failure's edit index, error code, and
  concise error text in the tool progress summary
- **AND** it SHALL keep the summary short enough for terminal status display
