## ADDED Requirements

### Requirement: Audit Mode Configuration

Deepy SHALL support TOML configuration for the default system audit mode.

#### Scenario: Config omits audit mode

- **WHEN** Deepy loads TOML configuration without an audit mode value
- **THEN** Deepy SHALL use `yolo` as the default audit mode for backward
  compatibility

#### Scenario: Config sets valid audit mode

- **WHEN** Deepy loads TOML configuration with audit mode `normal`, `auto`, or
  `yolo`
- **THEN** Deepy SHALL use that value as the default audit mode for new
  sessions

#### Scenario: Config sets invalid audit mode

- **WHEN** Deepy loads TOML configuration with an invalid audit mode value
- **THEN** Deepy SHALL fall back to the default audit mode
- **AND** Deepy SHALL make the invalid value discoverable through configuration
  validation or status diagnostics

#### Scenario: Runtime audit mode changes

- **WHEN** the user changes audit mode from an interactive runtime control such
  as `Shift+Tab`
- **THEN** Deepy SHALL update the active process audit mode immediately
- **AND** Deepy SHALL NOT persist the new mode to TOML configuration unless the
  user explicitly invokes a persistent configuration command

### Requirement: MCP Approval Override Configuration

Deepy SHALL support TOML configuration for MCP server/tool pairs that may be
auto-approved in `auto` audit mode.

#### Scenario: Config marks MCP tool as safe

- **WHEN** TOML configuration lists a specific MCP server/tool pair as safe for
  automatic approval
- **THEN** Deepy SHALL treat that pair as auto-approved only while the active
  audit mode is `auto` or `yolo`

#### Scenario: Config marks MCP wildcard unsafe

- **WHEN** TOML configuration does not list a specific MCP server/tool pair as
  safe
- **THEN** Deepy SHALL require approval for that MCP tool in `normal` and
  `auto` modes

#### Scenario: Config is written

- **WHEN** Deepy writes TOML configuration containing audit settings
- **THEN** the written config SHALL preserve existing model, context, logging,
  notify, tool, MCP, and UI settings
- **AND** the config file SHALL use permission mode `0600`
