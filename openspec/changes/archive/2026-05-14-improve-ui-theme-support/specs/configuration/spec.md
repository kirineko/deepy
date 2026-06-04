## ADDED Requirements

### Requirement: UI Theme Configuration

Deepy SHALL persist the user's terminal UI theme selection in TOML
configuration.

#### Scenario: Config without UI theme is loaded

- **WHEN** Deepy loads a TOML config that has no `[ui]` section or no `ui.theme`
  value
- **THEN** Deepy SHALL resolve the saved UI theme as `auto`

#### Scenario: Config has an invalid UI theme

- **WHEN** Deepy loads a TOML config whose `ui.theme` is not `auto`, `dark`, or
  `light`
- **THEN** Deepy SHALL resolve the saved UI theme as `auto`

#### Scenario: User shows configured theme

- **WHEN** a user runs `deepy config theme`
- **THEN** Deepy SHALL print the saved UI theme and the currently resolved
  runtime theme

#### Scenario: User updates configured theme

- **WHEN** a user runs `deepy config theme auto`, `deepy config theme dark`, or
  `deepy config theme light`
- **THEN** Deepy SHALL write the selected value to `ui.theme`
- **AND** it SHALL preserve existing model, context, logging, notify, and tool
  settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: User provides invalid configured theme

- **WHEN** a user runs `deepy config theme` with a value other than `auto`,
  `dark`, or `light`
- **THEN** Deepy SHALL return a non-zero status
- **AND** it SHALL NOT change the saved config

#### Scenario: User resets configuration

- **WHEN** a user runs `deepy config reset`
- **THEN** Deepy SHALL delete the existing TOML config file when it exists
- **AND** it SHALL guide the user through interactive setup again
- **AND** it SHALL write the replacement TOML config with permission mode `0600`

## MODIFIED Requirements

### Requirement: Config Initialization

Deepy SHALL provide non-interactive and interactive configuration commands.

#### Scenario: User initializes config

- **WHEN** a user runs `deepy config init`
- **THEN** Deepy SHALL support `--api-key`, `--model`, `--base-url`, `--theme`,
  and `--force`
- **AND** written config files SHALL use permission mode `0600`
- **AND** the written TOML SHALL include `ui.theme`

#### Scenario: User runs setup

- **WHEN** a user runs `deepy config setup`
- **THEN** Deepy SHALL show the DeepSeek API key page
- **AND** it SHALL collect the API key through password-style input
- **AND** it SHALL show numbered `auto`, `dark`, and `light` UI theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL write TOML with permission mode `0600`
- **AND** the written TOML SHALL include `ui.theme`
