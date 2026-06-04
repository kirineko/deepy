## ADDED Requirements

### Requirement: UI View Mode Configuration
Deepy SHALL persist the user's reasoning display view mode in TOML configuration with a unified default of concise.

#### Scenario: Config omits view mode
- **WHEN** Deepy loads a TOML config with no UI view mode setting
- **THEN** Deepy SHALL resolve the UI view mode as `concise`
- **AND** live reasoning transcript text SHALL be hidden by default

#### Scenario: Config sets concise view mode
- **WHEN** Deepy loads `[ui].view_mode = "concise"`
- **THEN** Deepy SHALL hide live reasoning transcript text in interactive UI surfaces
- **AND** it SHALL NOT disable provider reasoning behavior

#### Scenario: Config sets full view mode
- **WHEN** Deepy loads `[ui].view_mode = "full"`
- **THEN** Deepy SHALL show live reasoning transcript text in interactive UI surfaces that support reasoning display
- **AND** it SHALL NOT change provider reasoning strength

#### Scenario: Config has invalid view mode
- **WHEN** Deepy loads a TOML config whose UI view mode is not `concise` or `full`
- **THEN** Deepy SHALL resolve the UI view mode as `concise`
- **AND** it SHALL continue loading the rest of the configuration

#### Scenario: User toggles view mode
- **WHEN** a user changes the view mode through an interactive `/view` command
- **THEN** Deepy SHALL persist the selected view mode to TOML
- **AND** it SHALL preserve existing model, context, logging, notify, tools, MCP, input suggestion, and UI theme settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: Config is shown
- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include the resolved UI view mode
