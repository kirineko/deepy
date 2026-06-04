## ADDED Requirements

### Requirement: Textual Background Task Compatibility
The experimental Textual TUI SHALL preserve background task lifecycle guarantees without becoming the primary background task management UI.

#### Scenario: Background task exists in Textual TUI
- **WHEN** a managed background task is running while the experimental TUI is active
- **THEN** the TUI SHALL keep background output out of active thinking, assistant response, and foreground tool blocks
- **AND** it SHALL remain responsive to supported navigation and interrupt actions

#### Scenario: Textual TUI exits with background tasks
- **WHEN** the user exits the experimental TUI while managed background tasks are running
- **THEN** Deepy SHALL stop all running managed background tasks before the Textual app fully exits
- **AND** it SHALL return control to the user's terminal without requiring a separate cleanup command

#### Scenario: Textual command support is not yet implemented
- **WHEN** a user invokes `/ps` or `/stop` in the experimental TUI before Textual-native command handling exists for that command
- **THEN** the TUI SHALL show a clear unsupported-in-TUI message
- **AND** it SHALL NOT silently start a model turn for that slash command
