## MODIFIED Requirements

### Requirement: Textual Exit Summary Panel
The experimental Textual TUI SHALL show the redesigned exit summary panel with
local usage and DeepSeek session-cost information when it exits.

#### Scenario: User exits Textual TUI with slash command
- **WHEN** the user runs `/exit` or `/quit` in the experimental Textual TUI
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL show the redesigned exit summary panel after returning to
  the normal terminal
- **AND** it SHALL use the same usage and session-cost summary content as the
  stable terminal UI

#### Scenario: User exits Textual TUI with Ctrl+D
- **WHEN** the user confirms exit with Ctrl+D twice in the experimental Textual
  TUI
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL show the redesigned exit summary panel after returning to
  the normal terminal
- **AND** it SHALL use the same usage and session-cost summary content as the
  stable terminal UI

#### Scenario: Textual session cost cannot be computed
- **WHEN** the experimental Textual TUI exits
- **AND** Deepy cannot compute a reliable DeepSeek session-cost balance delta
- **THEN** the exit summary SHALL still render after returning to the normal
  terminal
- **AND** it SHALL keep local usage summary content visible
- **AND** it SHALL show concise cost unavailable text when cost tracking was
  attempted
