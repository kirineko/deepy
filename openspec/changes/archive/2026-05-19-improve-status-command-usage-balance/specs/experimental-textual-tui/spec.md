## ADDED Requirements

### Requirement: Textual Status View Usage And Balance
The experimental Textual TUI SHALL show the same local usage and DeepSeek balance summary in its `/status` auxiliary view while preserving the stable UI's `/status`-only balance lookup rule.

#### Scenario: User opens Textual status view
- **WHEN** the user invokes `/status` or selects the status command in the experimental Textual TUI
- **THEN** the TUI SHALL open a status view
- **AND** the view SHALL include active model, reasoning mode, current session, theme, loaded skills, session count, skill count, MCP status, and config path
- **AND** the view SHALL include active-session Token Usage when known
- **AND** the view SHALL include project-level Token Usage when known
- **AND** the view SHALL include Context Window occupancy when known
- **AND** the view SHALL include DeepSeek balance status returned for that `/status` invocation

#### Scenario: Textual status view cannot retrieve balance
- **WHEN** the user opens the Textual status view
- **AND** Deepy cannot retrieve DeepSeek balance
- **THEN** the view SHALL still open
- **AND** it SHALL show concise balance unavailable text
- **AND** it SHALL keep local status and usage information visible

#### Scenario: Textual non-status surfaces update
- **WHEN** the Textual TUI updates its status bar, side panel, welcome/help text, model-turn progress, local command progress, input suggestions, or usage blocks
- **THEN** it SHALL NOT call the DeepSeek balance endpoint
- **AND** it SHALL NOT show balance information outside the `/status` auxiliary view

### Requirement: Textual Exit Summary Panel
The experimental Textual TUI SHALL show the redesigned local-only exit summary panel when it exits.

#### Scenario: User exits Textual TUI with slash command
- **WHEN** the user runs `/exit` or `/quit` in the experimental Textual TUI
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL show the redesigned exit summary panel after returning to the normal terminal
- **AND** it SHALL use the same local usage summary content as the stable terminal UI
- **AND** it SHALL NOT call the DeepSeek balance endpoint

#### Scenario: User exits Textual TUI with Ctrl+D
- **WHEN** the user confirms exit with Ctrl+D twice in the experimental Textual TUI
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL show the redesigned exit summary panel after returning to the normal terminal
- **AND** it SHALL NOT call the DeepSeek balance endpoint
