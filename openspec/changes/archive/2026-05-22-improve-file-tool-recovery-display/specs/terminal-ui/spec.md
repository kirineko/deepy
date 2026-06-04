## ADDED Requirements

### Requirement: Safe Malformed Tool Argument Display
Deepy's stable terminal UI SHALL summarize malformed file-tool arguments without
dumping large raw mutation payloads into the transcript.

#### Scenario: Malformed write arguments are rendered
- **WHEN** Deepy renders a `write_file` tool call or output whose arguments are
  not valid JSON
- **THEN** the stable terminal UI SHALL show the normalized `[Write]` label
- **AND** it SHALL show a bounded malformed-arguments summary with the target
  path when it can be extracted safely
- **AND** it SHALL NOT render raw `content` body text solely because argument
  parsing failed

#### Scenario: Malformed edit arguments are rendered
- **WHEN** Deepy renders an `edit_text` tool call or output whose arguments are
  not valid JSON
- **THEN** the stable terminal UI SHALL show the normalized `[Edit]` label
- **AND** it SHALL show a bounded malformed-arguments summary with the target
  path when it can be extracted safely
- **AND** it SHALL NOT render raw `old_string` or `new_string` body text solely
  because argument parsing failed

#### Scenario: Malformed patch arguments are rendered
- **WHEN** Deepy renders an `apply_patch` tool call or output whose arguments are
  not valid JSON
- **THEN** the stable terminal UI SHALL show the normalized `[Patch]` label
- **AND** it SHALL show a bounded malformed-arguments summary with operation or
  target hints when they can be extracted safely
- **AND** it SHALL NOT render raw patch operation content solely because argument
  parsing failed

### Requirement: Retryable Tool Failure Presentation
Deepy's stable terminal UI SHALL present retryable argument failures differently
from blocking tool execution failures.

#### Scenario: Retryable invalid arguments are shown
- **WHEN** a tool result has `error_code="invalid_arguments"` and
  `retryable=true`
- **THEN** the stable terminal UI SHALL render the tool status as retryable or
  recoverable rather than as an ordinary blocking failure
- **AND** it SHALL include a concise recovery detail when available
- **AND** it SHALL keep the existing normalized tool label style

#### Scenario: Blocking mutation failure is shown
- **WHEN** a file mutation result fails because of a blocking safety or mutation
  error
- **THEN** the stable terminal UI SHALL continue to render it as a failed tool
  result
- **AND** it SHALL NOT imply that the mutation was recovered unless a later
  successful tool result explicitly reports success
