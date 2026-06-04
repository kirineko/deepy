## ADDED Requirements

### Requirement: Runtime Bottom Status Stability

Deepy SHALL render active-work runtime status as a terminal-safe single line that preserves critical progress information and bounded command detail.

#### Scenario: Long tool payload is displayed during active work

- **WHEN** a model turn is active and the current tool status includes a long parameter payload
- **THEN** Deepy SHALL keep the runtime status within the terminal-bottom row without uncontrolled wrapping or scrolling
- **AND** it SHALL keep the spinner, elapsed time, and interrupt affordance visible when the terminal width can fit them
- **AND** it SHALL prefer truncating payload detail before truncating the runtime prefix

#### Scenario: Long local command is displayed during execution

- **WHEN** a local `!cmd` command is running and the command text is longer than the available status payload width
- **THEN** Deepy SHALL continue to show command text in the runtime status when the terminal width can fit payload detail
- **AND** it SHALL tail-truncate the command payload so the beginning of the command remains visible
- **AND** it SHALL keep the spinner, elapsed time, and interrupt affordance visible when the terminal width can fit them

#### Scenario: Long shell tool command is displayed during execution

- **WHEN** a shell tool call is active and the shell command text is longer than the available status payload width
- **THEN** Deepy SHALL continue to show the shell tool label and command text in the runtime status when the terminal width can fit payload detail
- **AND** it SHALL tail-truncate the command payload so the beginning of the command remains visible
- **AND** it SHALL keep the spinner, elapsed time, and interrupt affordance visible when the terminal width can fit them

#### Scenario: Runtime payload contains control characters

- **WHEN** runtime status detail contains newlines, carriage returns, tabs, ANSI escape sequences, or non-printing control characters
- **THEN** Deepy SHALL normalize the detail to printable single-line status text before writing it to the terminal-bottom row
- **AND** the normalized status SHALL NOT move the cursor, clear terminal content, create extra terminal rows, or displace the protected runtime prefix

#### Scenario: Runtime status is rendered in a narrow terminal

- **WHEN** the terminal width is too narrow to fit the full runtime status
- **THEN** Deepy SHALL reduce payload detail before reducing the activity label
- **AND** it SHALL reduce the activity label before reducing the spinner, elapsed time, and interrupt affordance
- **AND** it SHALL still write no more than one terminal-bottom row
