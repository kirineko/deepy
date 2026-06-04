## ADDED Requirements

### Requirement: DeepSeek Model Configuration
Deepy SHALL persist and validate the active DeepSeek model in TOML
configuration.

#### Scenario: Default model is loaded
- **WHEN** Deepy loads config with no model name
- **THEN** Deepy SHALL use `deepseek-v4-pro` as the active model

#### Scenario: Supported model is loaded
- **WHEN** Deepy loads config with `model.name` set to `deepseek-v4-pro` or `deepseek-v4-flash`
- **THEN** Deepy SHALL use the configured model as the active model

#### Scenario: Invalid model is selected through Deepy commands
- **WHEN** a user attempts to select a model that is not in Deepy's supported DeepSeek model catalog
- **THEN** Deepy SHALL reject the value with a concise usage message
- **AND** it SHALL NOT change the saved config

### Requirement: Reasoning Mode Configuration
Deepy SHALL expose thinking behavior as a single user-facing reasoning mode with
values `none`, `high`, and `max` while persisting through existing TOML fields.

#### Scenario: Reasoning mode none is loaded
- **WHEN** Deepy loads config whose resolved reasoning mode is `none`
- **THEN** Deepy SHALL treat thinking as disabled

#### Scenario: Reasoning mode high is loaded
- **WHEN** Deepy loads config whose resolved reasoning mode is `high`
- **THEN** Deepy SHALL treat thinking as enabled
- **AND** it SHALL use `high` as the reasoning effort

#### Scenario: Reasoning mode max is loaded
- **WHEN** Deepy loads config whose resolved reasoning mode is `max`
- **THEN** Deepy SHALL treat thinking as enabled
- **AND** it SHALL use `max` as the reasoning effort

#### Scenario: Legacy thinking fields are loaded
- **WHEN** Deepy loads config that uses `model.thinking` and `model.reasoning_effort`
- **THEN** Deepy SHALL resolve `thinking = false` to reasoning mode `none`
- **AND** it SHALL resolve `thinking = true` with `reasoning_effort = "high"` to reasoning mode `high`
- **AND** it SHALL resolve `thinking = true` with `reasoning_effort = "max"` to reasoning mode `max`

#### Scenario: Missing thinking fields are loaded
- **WHEN** Deepy loads config with no explicit thinking setting
- **THEN** Deepy SHALL use reasoning mode `max`

#### Scenario: Reasoning mode is saved
- **WHEN** Deepy saves reasoning mode `none`, `high`, or `max`
- **THEN** Deepy SHALL update existing `model.thinking` and `model.reasoning_effort` fields instead of requiring a new TOML field

### Requirement: Targeted Model Config Updates
Deepy SHALL update model-related TOML settings without discarding unrelated
configuration.

#### Scenario: User saves model settings
- **WHEN** a user changes model or reasoning mode through Deepy commands
- **THEN** Deepy SHALL persist the selected model settings to TOML
- **AND** it SHALL use existing `[model]` fields for model name, thinking enabled state, and reasoning effort
- **AND** it SHALL preserve existing API key, base URL, context, logging, notify, tools, and UI theme settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: Config path is unknown
- **WHEN** a user attempts to save model settings and Deepy does not know the config path
- **THEN** Deepy SHALL report that the setting cannot be persisted
- **AND** it SHALL keep the current in-memory settings unchanged
