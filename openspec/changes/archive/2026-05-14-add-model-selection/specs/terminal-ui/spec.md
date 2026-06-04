## ADDED Requirements

### Requirement: Interactive Model Selection Command
Deepy SHALL provide an interactive `/model` command for selecting the active
DeepSeek model and reasoning mode with minimal typing.

#### Scenario: User opens model picker
- **WHEN** a user runs `/model` without arguments
- **THEN** Deepy SHALL show the current model and reasoning mode
- **AND** it SHALL present selectable supported DeepSeek models

#### Scenario: User selects model then reasoning mode
- **WHEN** a user selects a model from the `/model` picker
- **THEN** Deepy SHALL present selectable reasoning modes `none`, `high`, and `max`
- **AND** it SHALL save the selected model and reasoning mode only after both selections are complete

#### Scenario: User cancels model selection
- **WHEN** a user cancels the `/model` picker before completing both selections
- **THEN** Deepy SHALL leave the saved model settings unchanged
- **AND** it SHALL keep the current interactive session settings unchanged

#### Scenario: User completes model selection
- **WHEN** a user completes `/model` selection
- **THEN** Deepy SHALL persist the selected model settings
- **AND** subsequent turns in the same interactive process SHALL use the updated model settings
- **AND** Deepy SHALL print a concise confirmation with the active model and reasoning mode

### Requirement: Direct Model Command Forms
Deepy SHALL provide direct `/model` command forms for users who prefer explicit
arguments or are using non-picker terminal flows.

#### Scenario: User lists supported models
- **WHEN** a user runs `/model list`
- **THEN** Deepy SHALL list supported DeepSeek models
- **AND** it SHALL show the available reasoning modes `none`, `high`, and `max`

#### Scenario: User sets model directly
- **WHEN** a user runs `/model set deepseek-v4-pro` or `/model set deepseek-v4-flash`
- **THEN** Deepy SHALL persist the selected model
- **AND** it SHALL keep the current reasoning mode unless a reasoning mode is also selected

#### Scenario: User sets reasoning mode directly
- **WHEN** a user runs `/model reasoning none`, `/model reasoning high`, or `/model reasoning max`
- **THEN** Deepy SHALL persist the selected reasoning mode
- **AND** it SHALL keep the current model

#### Scenario: User provides invalid model command arguments
- **WHEN** a user runs `/model` with unsupported arguments, model, or reasoning mode
- **THEN** Deepy SHALL reject the command with a concise usage message
- **AND** it SHALL keep the saved model settings unchanged

### Requirement: Model Selection Discoverability
Deepy SHALL make model selection discoverable in the interactive terminal UI.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/model` SHALL be included as a built-in command

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/model` in the command list

#### Scenario: Startup screen is shown
- **WHEN** Deepy starts interactive mode
- **THEN** the welcome panel SHALL show the active model and reasoning mode
