## ADDED Requirements

### Requirement: Interactive Configuration Reset
Deepy SHALL reset terminal configuration without leaving partial files.

#### Scenario: Reset setup is interrupted
- **WHEN** a user exits or the prompt stream ends during `/reset` setup
- **THEN** Deepy SHALL report the cancellation without printing a traceback
- **AND** if a config file existed before `/reset`, Deepy SHALL restore that
  file unchanged
- **AND** if no config file existed before `/reset`, Deepy SHALL leave no
  partial config file behind

## MODIFIED Requirements

### Requirement: Startup Screen
Deepy SHALL show a compact welcome panel.

#### Scenario: User starts interactive mode

- **WHEN** Deepy starts
- **THEN** the welcome panel SHALL show the Deepy identity, version, provider,
  model, thinking settings, CWD, active UI theme, and only core commands

#### Scenario: First interactive startup has no saved theme

- **WHEN** Deepy starts interactive mode and no valid UI theme is saved
- **THEN** Deepy SHALL show numbered `auto`, `dark`, and `light` theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL persist the choice before rendering the welcome panel
- **AND** the welcome panel SHALL use the selected theme

### Requirement: Interactive Model Selection Command
Deepy SHALL provide an interactive `/model` command for selecting the active
provider, model, and provider-appropriate thinking mode with minimal typing.

#### Scenario: User opens model picker
- **WHEN** a user runs `/model` without arguments
- **THEN** Deepy SHALL show the current provider, model, and thinking mode
- **AND** it SHALL present selectable providers `DeepSeek`, `OpenRouter`, and `Xiaomi`
- **AND** `DeepSeek` SHALL be the default provider for new or legacy configurations

#### Scenario: User selects provider then model then thinking mode
- **WHEN** a user selects a provider from the `/model` picker
- **THEN** Deepy SHALL present only models supported by that provider
- **AND** after model selection it SHALL present only thinking choices supported by that provider
- **AND** DeepSeek SHALL offer `none`, `high`, and `max`
- **AND** OpenRouter SHALL offer `enabled`, `disabled`, `xhigh`, `high`,
  `medium`, `low`, `minimal`, and `none`
- **AND** Xiaomi MiMo SHALL offer `disabled` and `enabled`
- **AND** it SHALL save the selected provider, model, and thinking mode only after all selections are complete

#### Scenario: User cancels model selection
- **WHEN** a user cancels the `/model` picker before completing all selections
- **THEN** Deepy SHALL leave the saved model settings unchanged
- **AND** it SHALL keep the current interactive session settings unchanged

#### Scenario: User completes model selection
- **WHEN** a user completes `/model` selection
- **THEN** Deepy SHALL persist the selected provider, model, and thinking settings
- **AND** subsequent turns in the same interactive process SHALL use the updated provider and model settings
- **AND** Deepy SHALL print a concise confirmation with the active provider, model, and thinking mode

### Requirement: Direct Model Command Forms
Deepy SHALL provide direct `/model` command forms for users who prefer explicit
arguments or are using non-picker terminal flows.

#### Scenario: User lists supported models
- **WHEN** a user runs `/model list`
- **THEN** Deepy SHALL list supported models grouped by provider
- **AND** it SHALL show the available thinking choices for each provider family

#### Scenario: User sets DeepSeek model directly
- **WHEN** a user runs `/model set deepseek-v4-pro` or `/model set deepseek-v4-flash`
- **THEN** Deepy SHALL persist provider `deepseek` and the selected model
- **AND** it SHALL keep the current DeepSeek reasoning mode unless a reasoning mode is also selected

#### Scenario: User sets provider and MiMo model directly
- **WHEN** a user runs `/model set openrouter xiaomi/mimo-v2.5-pro high`
- **OR** a user runs `/model set openrouter xiaomi/mimo-v2.5 none`
- **OR** a user runs `/model set xiaomi mimo-v2.5-pro enabled`
- **OR** a user runs `/model set xiaomi mimo-v2.5 disabled`
- **THEN** Deepy SHALL persist the selected provider, model, and provider-appropriate thinking mode

#### Scenario: User sets provider directly
- **WHEN** a user runs `/model provider deepseek`, `/model provider openrouter`, or `/model provider xiaomi`
- **THEN** Deepy SHALL persist the selected provider
- **AND** it SHALL choose that provider's default model and default thinking mode when the current model is not valid for the selected provider

#### Scenario: User sets reasoning mode directly
- **WHEN** a user runs `/model reasoning none`, `/model reasoning high`, or `/model reasoning max`
- **THEN** Deepy SHALL persist the selected DeepSeek reasoning mode
- **AND** it SHALL keep the current provider and model when they support that reasoning mode

#### Scenario: User sets switch-only thinking directly
- **WHEN** a user runs `/model thinking enabled` or `/model thinking disabled`
- **THEN** Deepy SHALL persist the selected switch-only thinking mode when the current provider supports it
- **AND** it SHALL keep the current provider and model

#### Scenario: User provides invalid model command arguments
- **WHEN** a user runs `/model` with unsupported arguments, provider, model, or thinking mode
- **THEN** Deepy SHALL reject the command with a concise usage message
- **AND** it SHALL keep the saved model settings unchanged

### Requirement: Model Selection Discoverability
Deepy SHALL make provider and model selection discoverable in the interactive
terminal UI.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/model` SHALL be included as a built-in command

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/model` in the command list
- **AND** it SHALL describe provider, model, and thinking selection at a high level

#### Scenario: Startup screen is shown
- **WHEN** Deepy starts interactive mode
- **THEN** the welcome panel SHALL show the active provider, model, and thinking mode
