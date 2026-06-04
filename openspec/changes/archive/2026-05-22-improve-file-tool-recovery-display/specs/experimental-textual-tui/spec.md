## ADDED Requirements

### Requirement: Textual Recoverable Tool Attempt Display
The experimental TUI SHALL show recoverable malformed file-tool attempts without
making the transcript look like a completed failed edit when the model can
safely retry.

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
- **WHEN** a retryable malformed file-tool attempt is followed in the same model
  turn by a successful invocation of the same file tool for the same target path
  or target operation set
- **THEN** the TUI MAY fold the retryable attempt into the successful tool block
- **AND** the visible block SHALL indicate that the operation recovered after an
  argument retry
- **AND** the TUI SHALL NOT remove or rewrite persisted session history

#### Scenario: Blocking failure is not folded
- **WHEN** a file-tool attempt fails because of stale snapshots, missing
  freshness tokens, path policy, unsupported target type, approval policy,
  guardrails, absent matches, ambiguous matches, count mismatches, no-op edits,
  atomic write failure, backup failure, or partial commit
- **THEN** the TUI SHALL render the failure as a blocking failed tool block
- **AND** it SHALL NOT fold the failure into a later successful call unless the
  failure was explicitly marked retryable argument failure metadata

### Requirement: Textual Safe Malformed Argument Summaries
The experimental TUI SHALL summarize malformed file-tool arguments without
rendering large raw mutation payloads in tool blocks or details by default.

#### Scenario: Malformed file-tool call is shown
- **WHEN** the TUI renders a malformed `write_file`, `edit_text`, or
  `apply_patch` tool call
- **THEN** it SHALL show the normalized tool label and a bounded summary
- **AND** it SHALL include safely extracted target path or operation hints when
  available
- **AND** it SHALL NOT show raw large `content`, replacement text, or patch
  operation body text in the collapsed block

#### Scenario: User expands malformed argument details
- **WHEN** a user expands a malformed file-tool block
- **THEN** the TUI MAY show diagnostic details such as parse error location and
  recovery hint
- **AND** any raw argument text shown in details SHALL be bounded to avoid
  overwhelming the transcript
