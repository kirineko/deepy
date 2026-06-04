## MODIFIED Requirements

### Requirement: Textual Recoverable Tool Attempt Display
The experimental TUI SHALL show recoverable malformed v3 file-tool attempts
without making the transcript look like a completed failed edit when the model
can safely retry.

#### Scenario: Retryable invalid arguments update a tool block
- **WHEN** the TUI receives a tool output with `error_code="invalid_arguments"`
  and `retryable=true`
- **THEN** it SHALL update the corresponding tool block to a retryable or
  recoverable state
- **AND** the block SHALL remain visually distinct from blocking failed mutation
  states
- **AND** the block SHALL expose the concise recovery detail when details are
  expanded

#### Scenario: Recovered file-tool attempt is folded
- **WHEN** a retryable malformed `Read`, `Write`, or `Update` attempt is
  followed in the same model turn by a successful invocation of the same file
  tool for the same target path or target edit set
- **THEN** the TUI MAY fold the retryable attempt into the successful tool block
- **AND** the visible block SHALL indicate that the operation recovered after an
  argument retry
- **AND** the TUI SHALL NOT remove or rewrite persisted session history

#### Scenario: Blocking failure is not folded
- **WHEN** a `Write` or `Update` attempt fails because of stale or unread
  targets, path policy, unsupported target type, approval policy, guardrails,
  absent matches, ambiguous matches, count mismatches, no-op edits, atomic write
  failure, backup failure, rollback failure, or partial commit
- **THEN** the TUI SHALL render the failure as a blocking failed tool block
- **AND** it SHALL NOT fold the failure into a later successful call unless the
  failure was explicitly marked retryable argument failure metadata

### Requirement: Textual Safe Malformed Argument Summaries
The experimental TUI SHALL summarize malformed v3 file-tool arguments without
rendering large raw mutation payloads in tool blocks or details by default.

#### Scenario: Malformed file-tool call is shown
- **WHEN** the TUI renders a malformed `Read`, `Write`, or `Update` tool call
- **THEN** it SHALL show the normalized tool label and a bounded summary
- **AND** it SHALL include safely extracted target path, target count, or edit
  count hints when available
- **AND** it SHALL NOT show raw large `content`, `old`, `new`, or edit body text
  in the collapsed block

#### Scenario: User expands malformed argument details
- **WHEN** a user expands a malformed v3 file-tool block
- **THEN** the TUI MAY show diagnostic details such as parse error location and
  recovery hint
- **AND** any raw argument text shown in details SHALL be bounded to avoid
  overwhelming the transcript
