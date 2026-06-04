## MODIFIED Requirements

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL print complete thinking text immediately when it is
received.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a one-line terminal-bottom working status with elapsed time
- **AND** it SHALL show useful concise progress state when available
- **AND** the working status SHALL be cleared when the model turn completes
- **AND** the working status SHALL reserve no more than one fixed terminal-bottom
  row during active work
- **AND** the working status SHALL NOT render the structured prompt footer as a
  second fixed terminal-bottom row
- **AND** normal prompt submissions SHALL preserve the current transcript cursor
  position instead of forcing output to the bottom of the scrollable region
- **AND** AskUserQuestion continuation turns SHALL place resumed transcript
  output on cleared rows in the scrollable region with one spare row above the
  working status row when the prior user-answer prompt may have left recent
  question or answer text on the terminal's final lines
- **AND** the working status SHALL NOT include thinking transcript text
- **AND** thinking transcript output SHALL use the same bracketed label family as
  tool activity

#### Scenario: Local command is running

- **WHEN** a local `!cmd` command is in progress
- **THEN** Deepy SHALL show a one-line terminal-bottom running status with elapsed time and the
  command being executed
- **AND** the running status SHALL be cleared when the local command completes
- **AND** the running status SHALL reserve no more than one fixed terminal-bottom
  row during active work
- **AND** the running status SHALL NOT render the structured prompt footer as a
  second fixed terminal-bottom row

#### Scenario: Thinking delta is received

- **WHEN** Deepy receives thinking text for a model turn
- **THEN** Deepy SHALL immediately stream that thinking text to normal transcript output without waiting for a buffer-size threshold
- **AND** it SHALL print a visible `[Thinking]` label for the thinking block
- **AND** it SHALL NOT apply summary truncation to the thinking text
- **AND** it SHALL preserve readable line breaks in the printed thinking text
- **AND** it SHALL update the runtime status to a concise `thinking` state at most once per continuous thinking block

## ADDED Requirements

### Requirement: Submitted Prompt Transcript

Deepy SHALL keep submitted user prompts visually consistent with transcript
output.

#### Scenario: User submits a prompt

- **WHEN** the user submits a non-empty prompt in the interactive terminal
- **THEN** Deepy SHALL clear the prompt_toolkit-rendered submitted prompt before
  printing the transcript copy
- **AND** Deepy SHALL print exactly one transcript copy using the existing green
  user-input style
- **AND** multiline submitted prompts SHALL preserve their prompt marker on the
  first line and continuation indentation on later lines
- **AND** submitted prompts that occupy multiple terminal rows SHALL remain
  visible above the runtime status row when active work begins immediately after
  submission
