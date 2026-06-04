## ADDED Requirements

### Requirement: Manual Compact Command
Deepy SHALL expose an interactive `/compact` command for durable context compaction.

#### Scenario: User compacts active session
- **WHEN** a user runs `/compact` while an active session has compactable history
- **THEN** Deepy SHALL run durable session compaction
- **AND** it SHALL show concise progress while compaction is running
- **AND** it SHALL print a success message with before and after context token estimates

#### Scenario: User provides compact focus
- **WHEN** a user runs `/compact <focus>`
- **THEN** Deepy SHALL pass `<focus>` as the manual compaction focus instruction
- **AND** it SHALL keep the current session active after compaction succeeds

#### Scenario: User compacts without active session
- **WHEN** a user runs `/compact` before any session is active
- **THEN** Deepy SHALL show that there is no active session to compact
- **AND** it SHALL NOT start a new session

#### Scenario: Compact command fails
- **WHEN** manual compaction fails
- **THEN** Deepy SHALL show a concise failure message
- **AND** it SHALL keep the current session active and unchanged

### Requirement: Compact Command Discoverability
Deepy SHALL make the compact command discoverable in interactive command surfaces.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/compact` SHALL be included as a built-in command

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/compact [focus]` in the command list

#### Scenario: Startup screen is shown
- **WHEN** Deepy starts interactive mode
- **THEN** the welcome panel SHALL include `/compact` only if the compact command is part of the core command set displayed there

### Requirement: Automatic Compact Feedback
Deepy SHALL make automatic compaction visible without overwhelming normal chat output.

#### Scenario: Auto compaction runs before a turn
- **WHEN** Deepy automatically compacts context before sending a user prompt to the model
- **THEN** the terminal UI SHALL show a concise compaction status message
- **AND** the final usage footer SHALL reflect the compacted context estimate

#### Scenario: Auto compaction fails before a turn
- **WHEN** automatic compaction fails before the model request starts
- **THEN** the terminal UI SHALL show the compaction error
- **AND** it SHALL NOT render a misleading assistant response for that prompt
