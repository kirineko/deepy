## MODIFIED Requirements

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL print complete thinking text immediately when it is
received.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a one-line runtime working status with elapsed time
- **AND** it SHALL show useful concise progress state when available
- **AND** the working status visible text SHALL remain unchanged from the
  existing runtime status wording
- **AND** the working status SHALL render in the normal output flow rather than
  as a fixed terminal-bottom overlay
- **AND** the working status SHALL be cleared or superseded when normal
  transcript output or the completed model turn takes over
- **AND** the working status SHALL NOT set a terminal scroll region
- **AND** the working status SHALL NOT reserve or write to a fixed
  terminal-bottom row during active work
- **AND** the working status SHALL NOT render the structured prompt footer as a
  second fixed terminal-bottom row
- **AND** normal prompt submissions SHALL NOT perform runtime-status-specific
  bottom-row anchoring after printing submitted user input
- **AND** AskUserQuestion continuation turns SHALL NOT perform
  runtime-status-specific bottom-row anchoring before resumed transcript output
- **AND** runtime-status-specific POSIX or Windows cursor-row probing SHALL NOT
  be required to place resumed output
- **AND** the working status SHALL use segment-level foreground styling to
  distinguish semantic parts such as spinner, elapsed time, interrupt hint,
  detail label, and payload
- **AND** the working status SHALL NOT use a full-line background color
- **AND** the working status SHALL NOT include thinking transcript text
- **AND** thinking transcript output SHALL use the same bracketed label family as
  tool activity

#### Scenario: Local command is running

- **WHEN** a local `!cmd` command is in progress
- **THEN** Deepy SHALL show a one-line running status with elapsed time and the
  command being executed
- **AND** the running status visible text SHALL remain unchanged from the
  existing runtime status wording
- **AND** the running status SHALL render in the normal output flow rather than
  as a fixed terminal-bottom overlay
- **AND** the running status SHALL be cleared or superseded when the local
  command completes
- **AND** the running status SHALL NOT set a terminal scroll region
- **AND** the running status SHALL NOT reserve or write to a fixed
  terminal-bottom row during active work
- **AND** the running status SHALL NOT render the structured prompt footer as a
  second fixed terminal-bottom row
- **AND** submitted local-command input SHALL NOT perform
  runtime-status-specific bottom-row anchoring before command output
- **AND** runtime-status-specific POSIX or Windows cursor-row probing SHALL NOT
  be required to place command output
- **AND** the running status SHALL use segment-level foreground styling to
  distinguish semantic parts such as spinner, elapsed time, interrupt hint,
  `local command`, and command payload
- **AND** the running status SHALL NOT use a full-line background color

#### Scenario: Thinking delta is received

- **WHEN** Deepy receives thinking text for a model turn
- **THEN** Deepy SHALL immediately stream that thinking text to normal transcript output without waiting for a buffer-size threshold
- **AND** it SHALL print a visible `[Thinking]` label for the thinking block
- **AND** it SHALL NOT apply summary truncation to the thinking text
- **AND** it SHALL preserve readable line breaks in the printed thinking text
- **AND** it SHALL update the runtime status to a concise `thinking` state at most once per continuous thinking block
