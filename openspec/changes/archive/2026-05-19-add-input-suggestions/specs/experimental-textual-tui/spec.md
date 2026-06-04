## ADDED Requirements

### Requirement: Textual Input Suggestion Ghost Text
The experimental Textual TUI SHALL provide input suggestion ghost text that
matches the stable UI semantics as closely as Textual permits.

#### Scenario: Suggestion becomes visible in Textual prompt
- **WHEN** an eligible input suggestion is available
- **AND** the Textual prompt input buffer is empty
- **THEN** the TUI SHALL render the suggestion in the prompt area as muted
  ghost text
- **AND** the ghost text SHALL NOT be rendered as a slash-command or file-mention
  dropdown entry

#### Scenario: Textual user accepts with Tab
- **WHEN** ghost-text input suggestion is visible in the Textual TUI
- **AND** the user presses Tab
- **THEN** the TUI SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: Textual user accepts with Right Arrow
- **WHEN** ghost-text input suggestion is visible in the Textual TUI
- **AND** the user presses Right Arrow
- **THEN** the TUI SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: Textual user presses Enter with visible suggestion
- **WHEN** ghost-text input suggestion is visible in the Textual TUI
- **AND** the input buffer is empty
- **AND** the user presses Enter
- **THEN** the TUI SHALL NOT insert or submit the suggestion
- **AND** Enter SHALL retain the Textual prompt's existing submit behavior

#### Scenario: Textual prompt has another suggestion surface
- **WHEN** slash command suggestions or file mention suggestions are visible in
  the Textual prompt
- **THEN** those existing suggestion surfaces SHALL retain their selection
  behavior
- **AND** input suggestion ghost text SHALL NOT overlap them incoherently

#### Scenario: Textual ghost rendering is constrained
- **WHEN** Textual `TextArea` internals prevent exact inline ghost-text
  rendering
- **THEN** Deepy SHALL still render the suggestion in the prompt area with ghost
  styling
- **AND** it SHALL preserve the same Tab, Right Arrow, Enter, and dismissal
  semantics
