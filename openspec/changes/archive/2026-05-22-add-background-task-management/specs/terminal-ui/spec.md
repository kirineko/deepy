## ADDED Requirements

### Requirement: Background Task Slash Commands
Deepy's stable terminal UI SHALL provide `/ps` and `/stop` commands for managing Deepy-owned background tasks.

#### Scenario: User lists background tasks
- **WHEN** a user runs `/ps`
- **THEN** Deepy SHALL print running and recent terminal background tasks
- **AND** each task row SHALL include task id, status, elapsed or finished time, and concise command or description
- **AND** the output SHALL include enough information for the user to request task output or identify work to stop

#### Scenario: User lists tasks when none exist
- **WHEN** a user runs `/ps` and Deepy has no managed background tasks
- **THEN** Deepy SHALL print a concise no-background-tasks message
- **AND** it SHALL keep the active session unchanged

#### Scenario: User stops background tasks
- **WHEN** a user runs `/stop`
- **THEN** Deepy SHALL request termination for all running background tasks owned by the current Deepy process/session
- **AND** it SHALL print a concise summary of tasks that were requested to stop
- **AND** it SHALL keep terminal tasks visible in `/ps` after they settle

#### Scenario: User stops when no tasks are running
- **WHEN** a user runs `/stop` and no managed background tasks are running
- **THEN** Deepy SHALL print a concise no-running-background-tasks message
- **AND** it SHALL keep the active session unchanged

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL list `/ps` and `/stop` with concise descriptions

### Requirement: Background Task Status Non-Interference
Deepy's stable terminal UI SHALL keep background task status separate from active model thinking and response rendering.

#### Scenario: Background task runs while prompt is idle
- **WHEN** one or more background tasks are running while Deepy is waiting for input
- **THEN** Deepy MAY show a concise background task count in prompt/status context
- **AND** it SHALL NOT print unsolicited task output into the transcript

#### Scenario: Background task runs during model turn
- **WHEN** one or more background tasks are running during a foreground model turn
- **THEN** Deepy SHALL preserve the foreground working status, thinking stream, tool display, and assistant response rendering
- **AND** background task output SHALL remain hidden unless explicitly inspected

### Requirement: Background Task Exit Cleanup
Deepy's stable terminal UI SHALL clean up background tasks during interactive exit.

#### Scenario: User exits with slash command
- **WHEN** the user runs `/exit` or `/quit`
- **THEN** Deepy SHALL stop all running managed background tasks before closing the interactive runtime
- **AND** it SHALL still print the normal exit summary

#### Scenario: User exits with Ctrl+D confirmation
- **WHEN** the user confirms exit with Ctrl+D while background tasks are running
- **THEN** Deepy SHALL stop all running managed background tasks before closing the interactive runtime
- **AND** it SHALL still print the normal exit summary

#### Scenario: User interrupts the terminal UI
- **WHEN** the user exits the stable terminal UI with KeyboardInterrupt
- **THEN** Deepy SHALL attempt bounded cleanup of all running managed background tasks before returning control to the terminal
