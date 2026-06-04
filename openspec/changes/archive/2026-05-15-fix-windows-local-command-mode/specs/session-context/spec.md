## MODIFIED Requirements

### Requirement: Local Command Transcript Persistence
Deepy SHALL persist local command-mode input and output in the active session so
later model turns can use the command result as context.

#### Scenario: Local command completes
- **WHEN** a local command-mode command completes
- **THEN** Deepy SHALL append the literal `!` command input to the active session
  as a user item
- **AND** it SHALL append a synthetic assistant shell tool call item for the
  command
- **AND** it SHALL append a matching synthetic shell tool result item containing
  the command result

#### Scenario: Later model turn replays session
- **WHEN** Deepy prepares session history for a later model turn
- **THEN** the previously recorded local command transcript SHALL be included in
  the replayed session input
- **AND** the model SHALL be able to see both the local command and its stored
  output

#### Scenario: Local command output is stored
- **WHEN** Deepy stores a local command result in the session
- **THEN** it SHALL apply a context-storage output limit independent of the
  terminal display limit
- **AND** stored metadata SHALL indicate when output was truncated for context

#### Scenario: Windows local command output is stored
- **WHEN** Deepy stores a Windows local command result in the session
- **THEN** the stored shell output SHALL decode Windows-native command output
  into readable Unicode text before persistence
- **AND** it SHALL use normalized line endings
- **AND** it SHALL NOT include terminal control sequences that were removed from
  user-facing display
- **AND** it SHALL preserve printable Unicode command output

#### Scenario: Local command result metadata is stored
- **WHEN** Deepy stores a local command result
- **THEN** the synthetic shell result SHALL include command-mode metadata such as
  cwd, shell kind, command dialect, TTY mode, exit code, duration, and
  interruption or timeout state when available

#### Scenario: Local command does not call the model
- **WHEN** a local command-mode command is handled
- **THEN** Deepy SHALL NOT record model token usage for that command
- **AND** it SHALL update local context estimates from the appended session
  records so the status footer reflects pending context

#### Scenario: Local command history is shown
- **WHEN** a session containing local command-mode records is displayed or
  resumed
- **THEN** Deepy SHALL render the synthetic shell result using the existing
  shell output display path
