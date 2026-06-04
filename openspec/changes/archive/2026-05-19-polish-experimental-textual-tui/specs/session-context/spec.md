## ADDED Requirements

### Requirement: Textual Session Commands
The experimental Textual TUI SHALL expose session lifecycle commands through
Textual-native surfaces.

#### Scenario: User starts a new TUI session
- **WHEN** a user invokes `/new` in the experimental TUI
- **THEN** the TUI SHALL clear the active session id
- **AND** it SHALL reset loaded per-session TUI state that should not carry into
  the new conversation
- **AND** it SHALL keep global settings unchanged

#### Scenario: User lists TUI sessions
- **WHEN** a user invokes `/sessions` in the experimental TUI
- **THEN** the TUI SHALL show project session entries in a navigable Textual
  surface
- **AND** each entry SHALL include session id, title or first prompt, status,
  timestamp, and available history estimate when known

#### Scenario: User resumes a TUI session
- **WHEN** a user selects a session from `/resume` or the sessions surface
- **THEN** the TUI SHALL set that session as active
- **AND** it SHALL restore visible transcript history from the session when
  available
- **AND** subsequent prompts SHALL continue that session id

#### Scenario: User cancels session selection
- **WHEN** a user cancels the session picker
- **THEN** the TUI SHALL keep the previous active session unchanged
- **AND** focus SHALL return to the prompt or prior conversation surface

### Requirement: Textual Manual Compaction
The experimental Textual TUI SHALL expose manual session compaction for the
active session.

#### Scenario: User compacts active TUI session
- **WHEN** a user invokes `/compact` in the experimental TUI with an active
  session
- **THEN** Deepy SHALL run the existing durable session compaction flow
- **AND** the TUI SHALL show running, success, no-op, or failure state in the
  transcript or status surface
- **AND** the active session id SHALL remain usable after compaction

#### Scenario: User provides compaction focus
- **WHEN** a user invokes `/compact` with a focus instruction
- **THEN** the TUI SHALL pass the focus instruction to the compaction flow
- **AND** the compaction summary SHALL prioritize that focus according to the
  existing session-context contract

#### Scenario: User compacts without active session
- **WHEN** a user invokes `/compact` before a TUI session exists
- **THEN** the TUI SHALL report that there is no active session to compact
- **AND** it SHALL NOT start a model turn

### Requirement: Textual Local Command Session Persistence
The experimental Textual TUI SHALL persist local command-mode input and output
using the same synthetic shell transcript records as the stable terminal UI.

#### Scenario: TUI local command completes
- **WHEN** a TUI local command-mode command completes
- **THEN** Deepy SHALL append the literal `!` command input to the active
  session as a user item
- **AND** it SHALL append a synthetic assistant shell tool call item
- **AND** it SHALL append a matching synthetic shell tool result item
  containing the command result
- **AND** the TUI SHALL update its active session id when persistence creates a
  new session

#### Scenario: TUI local command output is stored
- **WHEN** the TUI stores a local command result in the session
- **THEN** it SHALL apply the same context-storage output limit used by stable
  local command mode
- **AND** stored metadata SHALL indicate when output was truncated for context

#### Scenario: TUI Windows local command output is stored
- **WHEN** the TUI stores a Windows local command result in the session
- **THEN** the stored shell output SHALL decode Windows-native command output
  into readable Unicode text before persistence
- **AND** it SHALL use normalized line endings
- **AND** it SHALL NOT include terminal control sequences that were removed from
  user-facing display

#### Scenario: TUI resumes local command history
- **WHEN** the TUI restores a session containing local command-mode records
- **THEN** it SHALL render the synthetic shell result through the same shell
  output display path used for model-invoked shell tool results
