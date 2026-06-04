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

#### Scenario: User clears draft with Esc then timely delete
- **WHEN** a user is editing a non-empty Textual TUI prompt
- **AND** the user presses Esc followed by Delete or Backspace within 2 seconds
- **THEN** the TUI SHALL clear the entire prompt draft
- **AND** it SHALL refresh prompt-adjacent suggestion surfaces for the empty
  draft
- **AND** a single Delete or Backspace without the preceding Esc SHALL keep the
  normal character deletion behavior

#### Scenario: Esc delete shortcut expires
- **WHEN** a user presses Esc while editing a non-empty Textual TUI prompt
- **AND** more than 2 seconds elapse before the user presses Delete or Backspace
- **THEN** the TUI SHALL keep the normal character deletion behavior
- **AND** it SHALL NOT clear the entire prompt draft

#### Scenario: User opens slash command discovery
- **WHEN** a user types `/` at the beginning of the prompt
- **THEN** the TUI SHALL expose available Deepy slash commands in a selectable
  Textual surface

#### Scenario: User references project files
- **WHEN** a user starts a file mention with `@`
- **THEN** the TUI SHALL provide a project-file mention affordance
- **AND** selected file mentions SHALL be inserted into the prompt text

#### Scenario: Textual short file mention fragment searches nested paths
- **WHEN** a user types a short non-empty Textual TUI `@` fragment without a
  directory separator
- **THEN** the TUI SHALL include matching nested files and directories from the
  active project root in the completion candidates
- **AND** the search SHALL remain bounded by the same candidate limit, cache,
  ignore rules, symlink exclusions, and project-root containment rules used by
  file mention discovery
- **AND** bare `@` SHALL remain limited to top-level project candidates
