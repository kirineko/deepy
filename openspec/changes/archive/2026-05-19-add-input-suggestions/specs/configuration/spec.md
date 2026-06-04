## ADDED Requirements

### Requirement: Input Suggestion Configuration
Deepy SHALL persist input suggestion enablement in TOML configuration with a
default of enabled.

#### Scenario: Config omits input suggestion setting
- **WHEN** Deepy loads a TOML config with no input suggestion enabled setting
- **THEN** Deepy SHALL resolve input suggestions as enabled

#### Scenario: Config disables input suggestions
- **WHEN** Deepy loads a TOML config whose input suggestion enabled setting is
  false
- **THEN** Deepy SHALL disable input suggestion generation and display for
  interactive sessions

#### Scenario: User toggles input suggestions
- **WHEN** a user runs `/input-suggestion` in an interactive terminal UI
- **THEN** Deepy SHALL persist the toggled enabled state to TOML
- **AND** it SHALL preserve existing model, context, logging, notify, tools, MCP,
  and UI theme settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: Config is shown
- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include the resolved input suggestion enabled state
- **AND** it SHALL NOT expose any user-customizable suggestion model field
