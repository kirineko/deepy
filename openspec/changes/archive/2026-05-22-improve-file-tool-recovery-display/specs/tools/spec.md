## ADDED Requirements

### Requirement: Recoverable Tool Argument Handling
Deepy SHALL conservatively recover high-confidence malformed built-in tool
arguments before returning an invalid-arguments tool failure.

#### Scenario: Unquoted snapshot id is repaired
- **WHEN** the model invokes a built-in file mutation tool with otherwise valid
  JSON-like arguments whose only parse failure is an unquoted `snapshot_<number>`
  value in a `snapshot_id` field
- **THEN** Deepy SHALL repair the value to a JSON string before invoking the tool
- **AND** it SHALL validate the repaired arguments against the tool schema before
  executing the tool
- **AND** the tool result metadata SHALL identify that argument repair was
  applied

#### Scenario: Unquoted snippet id is repaired
- **WHEN** the model invokes `edit_text` with otherwise valid JSON-like
  arguments whose only parse failure is an unquoted `snippet_<number>` value in
  a `snippet_id` field
- **THEN** Deepy SHALL repair the value to a JSON string before invoking
  `edit_text`
- **AND** it SHALL validate the repaired arguments against the tool schema before
  executing the tool

#### Scenario: Simple JSON-like literals are repaired
- **WHEN** a built-in tool receives otherwise valid JSON-like arguments
- **AND** the only malformed tokens are Python-style `None`, `True`, or `False`
  values or trailing commas
- **THEN** Deepy MAY repair those tokens to valid JSON equivalents
- **AND** it SHALL validate the repaired arguments before executing the tool

#### Scenario: Unsafe argument repair is rejected
- **WHEN** a built-in tool receives malformed arguments whose repair would require
  guessing string delimiters, escaping, nested structure, `content`,
  `old_string`, `new_string`, `old_text`, `new_text`, `anchor`, shell commands,
  or patch operation bodies
- **THEN** Deepy SHALL NOT execute the tool
- **AND** it SHALL return a structured invalid-arguments result
- **AND** the result metadata SHALL mark the failure as retryable when a valid
  retry can safely resolve it

### Requirement: Numeric Snapshot Freshness Tokens
Deepy SHALL expose and accept numeric managed snapshot freshness tokens in
addition to existing snapshot ids and content hashes.

#### Scenario: Read returns numeric snapshot token
- **WHEN** `read_file` records a managed file snapshot
- **THEN** the result metadata SHALL include the existing `snapshot_id`
- **AND** it SHALL include the existing content hash
- **AND** it SHALL include a numeric `snapshot_token` representing the same
  runtime-local snapshot

#### Scenario: Write replacement accepts snapshot token
- **WHEN** the model invokes `write_file` for an existing file with
  `overwrite=true`
- **AND** it provides a fresh `snapshot_token` returned by `read_file`
- **THEN** Deepy SHALL treat the token as an equivalent freshness token for the
  current tool runtime
- **AND** stale, missing, or mismatched tokens SHALL still reject the write

#### Scenario: Patch replacement accepts snapshot token
- **WHEN** the model invokes `apply_patch` with a `replace_file` operation for an
  existing file
- **AND** the operation provides `overwrite=true` and a fresh `snapshot_token`
- **THEN** Deepy SHALL treat the token as an equivalent freshness token for that
  replacement operation
- **AND** stale, missing, or mismatched tokens SHALL still reject the patch during
  preflight

### Requirement: Retryable Tool Failure Metadata
Deepy SHALL distinguish recoverable argument failures from unrecoverable tool
failures through structured metadata.

#### Scenario: Invalid arguments can be retried
- **WHEN** a built-in tool rejects malformed arguments before executing any side
  effect
- **AND** a syntactically valid retry could safely resolve the failure
- **THEN** the result metadata SHALL include `error_code="invalid_arguments"`
- **AND** it SHALL include `retryable=true`
- **AND** it SHALL include a concise recovery hint

#### Scenario: Safety failures remain blocking
- **WHEN** a file mutation fails because of stale snapshots, missing freshness
  tokens for existing-file replacement, path policy, unsupported target type,
  approval policy, guardrails, absent matches, ambiguous matches, count
  mismatches, no-op edits, atomic write failure, backup failure, or partial
  commit
- **THEN** Deepy SHALL NOT mark the result as a repaired argument success
- **AND** it SHALL preserve the existing blocking failure semantics and metadata
  for that error class
