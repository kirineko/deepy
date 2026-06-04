## ADDED Requirements

### Requirement: Stable Input Suggestion Ghost Text
Deepy's stable prompt-toolkit terminal UI SHALL render input suggestions as
prompt-area ghost text without changing existing prompt submission semantics.

#### Scenario: Suggestion becomes visible
- **WHEN** an eligible input suggestion is available
- **AND** the stable terminal prompt input buffer is empty
- **THEN** Deepy SHALL show the suggestion in the input area using muted or
  placeholder-style ghost text
- **AND** it SHALL keep the normal prompt footer and transcript readable

#### Scenario: User accepts with Tab
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the user presses Tab
- **THEN** Deepy SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: User accepts with Right Arrow
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the user presses Right Arrow
- **THEN** Deepy SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: User presses Enter with visible suggestion
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the input buffer is empty
- **AND** the user presses Enter
- **THEN** Deepy SHALL NOT insert or submit the suggestion
- **AND** Enter SHALL retain the stable prompt's existing submit behavior

#### Scenario: User starts editing
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the user types, pastes, opens another completion surface, submits a
  prompt, starts a local command, or starts a model turn
- **THEN** Deepy SHALL clear the visible suggestion

### Requirement: Input Suggestion Slash Command
Deepy's interactive terminal UIs SHALL expose `/input-suggestion` as the user
control for input suggestion enablement.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/input-suggestion` SHALL be included as a built-in command
- **AND** its description SHALL indicate that it toggles input suggestions

#### Scenario: User toggles input suggestions
- **WHEN** a user runs `/input-suggestion` with no arguments
- **THEN** Deepy SHALL toggle the persisted input suggestion enabled state
- **AND** it SHALL update the current interactive process to use the new state
- **AND** it SHALL print a concise confirmation of whether input suggestions
  are enabled or disabled

#### Scenario: User provides unsupported arguments
- **WHEN** a user runs `/input-suggestion` with any argument
- **THEN** Deepy SHALL reject the command with a concise usage message
- **AND** it SHALL leave the saved input suggestion setting unchanged

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/input-suggestion` in the command list
