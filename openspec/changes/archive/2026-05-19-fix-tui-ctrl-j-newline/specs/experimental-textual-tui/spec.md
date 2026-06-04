## MODIFIED Requirements

### Requirement: Textual Prompt Input
The experimental TUI SHALL provide Textual-native prompt input that preserves
Deepy's core input model.

#### Scenario: User submits prompt
- **WHEN** a user enters text and presses Enter
- **THEN** the TUI SHALL submit the prompt to the active Deepy session
- **AND** it SHALL add the submitted prompt to the transcript

#### Scenario: User inserts newline
- **WHEN** a user presses Ctrl+J while editing the prompt
- **THEN** the TUI SHALL insert a newline into the prompt
- **AND** it SHALL NOT submit the prompt

#### Scenario: User opens slash command discovery
- **WHEN** a user types `/` at the beginning of the prompt
- **THEN** the TUI SHALL expose available Deepy slash commands in a selectable
  Textual surface

#### Scenario: User references project files
- **WHEN** a user starts a file mention with `@`
- **THEN** the TUI SHALL provide a project-file mention affordance
- **AND** selected file mentions SHALL be inserted into the prompt text
