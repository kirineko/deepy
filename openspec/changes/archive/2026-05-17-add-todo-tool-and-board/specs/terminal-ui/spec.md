## ADDED Requirements

### Requirement: Todo Board Rendering

Deepy SHALL render the active todo plan as a compact terminal board instead of
raw tool JSON.

#### Scenario: Todo plan is created or updated

- **WHEN** a `todo_write` result updates the current todo plan
- **THEN** Deepy SHALL render a terminal todo board containing the current
  progress count and task list
- **AND** the board SHALL show pending, in-progress, and completed statuses with
  distinct visual markers
- **AND** the board SHALL use the active terminal theme palette for readable
  dark and light background output

#### Scenario: Todo board summary is rendered

- **WHEN** the todo board is rendered for a non-empty todo plan
- **THEN** Deepy SHALL show the number of completed items and total items
- **AND** it SHALL show the current `in_progress` item when one exists
- **AND** it SHALL fall back to the first pending item when no item is marked
  `in_progress`

#### Scenario: Todo board is rendered in a narrow terminal

- **WHEN** the terminal width or height cannot fit the complete todo board
- **THEN** Deepy SHALL truncate or compact the board without breaking table or
  panel layout
- **AND** it SHALL preserve the progress count and current-task summary

#### Scenario: Todo tool output appears in history

- **WHEN** Deepy renders session history containing todo updates
- **THEN** it SHALL render the latest relevant todo state as a readable board or
  compact progress summary
- **AND** it SHALL NOT replay verbose raw todo JSON as ordinary transcript text

### Requirement: Todo Board Separation From Footer

Deepy SHALL keep todo board rendering separate from the interactive status
footer.

#### Scenario: Model turn is running

- **WHEN** a model turn is in progress and a todo plan exists
- **THEN** Deepy SHALL preserve the existing bottom footer layout and colors
- **AND** it SHALL NOT add the full todo list to the footer
- **AND** runtime status such as elapsed time, interrupt hint, thinking, and tool
  state SHALL remain in the dedicated runtime status line

#### Scenario: Model turn completes

- **WHEN** a model turn completes after todo updates
- **THEN** Deepy SHALL keep the latest todo board or compact todo summary
  visually consistent with the running-state board
- **AND** it SHALL NOT change the persistent footer style because todo state
  changed
