## ADDED Requirements

### Requirement: Interactive Status Command
Deepy SHALL provide a discoverable `/status` command in the stable interactive terminal UI that renders a compact status panel with local usage, context, runtime, and DeepSeek balance information.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds stable interactive slash command completions
- **THEN** `/status` SHALL be included as a built-in command
- **AND** its description SHALL explain that it shows status, usage, and DeepSeek balance

#### Scenario: Help lists status command
- **WHEN** the user runs `/help` in the stable interactive terminal UI
- **THEN** Deepy SHALL list `/status`
- **AND** the help text SHALL describe the command as a status, usage, and balance view

#### Scenario: User runs status command
- **WHEN** the user runs `/status` in the stable interactive terminal UI
- **THEN** Deepy SHALL render a compact status panel
- **AND** the panel SHALL include the active model and reasoning mode
- **AND** the panel SHALL include whether an API key is configured without printing the key
- **AND** the panel SHALL include active-session Token Usage when an active session exists and usage is known
- **AND** the panel SHALL include project-level Token Usage when persisted session usage is known
- **AND** the panel SHALL include Context Window occupancy when known
- **AND** the panel SHALL include project root, session count, skill count, and MCP status
- **AND** the panel SHALL include DeepSeek balance status returned for that `/status` invocation

#### Scenario: Balance lookup fails
- **WHEN** the user runs `/status`
- **AND** Deepy cannot retrieve DeepSeek balance because of missing configuration, unsupported API host, timeout, network failure, authentication failure, or malformed response
- **THEN** Deepy SHALL still render the rest of the status panel
- **AND** it SHALL show concise balance unavailable text
- **AND** it SHALL NOT print a traceback

#### Scenario: Other terminal surfaces render status
- **WHEN** Deepy renders welcome content, prompt footer content, working status content, local command status content, usage footers, or normal model-turn output
- **THEN** Deepy SHALL NOT call the DeepSeek balance endpoint
- **AND** it SHALL NOT add balance information to those frequently rendered surfaces

### Requirement: Redesigned Exit Summary Panel
Deepy SHALL render a compact, redesigned local-only exit summary panel in the stable interactive terminal UI.

#### Scenario: User exits stable interactive session
- **WHEN** the user exits the stable interactive terminal UI through `/exit`, `/quit`, or confirmed Ctrl+D
- **THEN** Deepy SHALL render an exit summary panel
- **AND** the panel SHALL use the same compact visual language and label hierarchy as the `/status` panel
- **AND** the panel SHALL include local cumulative model usage when known
- **AND** the panel SHALL include input-suggestion usage when known
- **AND** the panel SHALL include the active model and session identity when known
- **AND** the panel SHALL remain readable when usage is unknown
- **AND** the panel SHALL NOT call the DeepSeek balance endpoint
- **AND** the panel SHALL NOT display DeepSeek balance information

#### Scenario: Exit summary has no usage
- **WHEN** the user exits a stable interactive session with no known usage
- **THEN** Deepy SHALL still render a concise exit summary panel
- **AND** it SHALL omit empty usage tables instead of showing zero-filled noise

## MODIFIED Requirements

### Requirement: Experimental TUI Exit Summary
The experimental Textual TUI SHALL provide a clean exit path consistent with
Deepy's stable terminal experience.

#### Scenario: User exits active TUI session
- **WHEN** the user exits the experimental TUI through `/exit`, `/quit`, or confirmed Ctrl+D
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL return terminal control without leaving a stale full-screen
  status area
- **AND** it SHALL show the redesigned concise exit summary panel after leaving the full-screen app
- **AND** the panel SHALL use the same compact local-only exit summary content as the stable terminal UI
- **AND** it SHALL NOT call the DeepSeek balance endpoint
- **AND** it SHALL NOT display DeepSeek balance information
