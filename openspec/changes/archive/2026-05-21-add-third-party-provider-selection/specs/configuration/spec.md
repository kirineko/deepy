## ADDED Requirements

### Requirement: Provider Selection Configuration
Deepy SHALL support an optional provider selection in TOML model configuration.

#### Scenario: Config has explicit provider
- **WHEN** Deepy loads config with `model.provider` set to `deepseek`, `openrouter`, or `xiaomi`
- **THEN** Deepy SHALL resolve that provider as the active provider
- **AND** it SHALL validate model and thinking choices against that provider's catalog

#### Scenario: Config has no provider and known base URL
- **WHEN** Deepy loads config without `model.provider`
- **AND** `model.base_url` points at official DeepSeek, OpenRouter, or Xiaomi MiMo hosts
- **THEN** Deepy SHALL infer `deepseek`, `openrouter`, or `xiaomi` respectively

#### Scenario: Config has no provider and unknown base URL
- **WHEN** Deepy loads config without `model.provider`
- **AND** `model.base_url` does not match a known provider host
- **THEN** Deepy SHALL preserve the existing DeepSeek-style behavior
- **AND** it SHALL NOT expose a separate user-facing compatibility provider

#### Scenario: Provider default base URLs are used
- **WHEN** Deepy writes provider-aware configuration without a user-specified base URL
- **THEN** it SHALL use `https://api.deepseek.com` for `deepseek`
- **AND** it SHALL use `https://openrouter.ai/api/v1` for `openrouter`
- **AND** it SHALL use `https://api.xiaomimimo.com/v1` for `xiaomi`

## MODIFIED Requirements

### Requirement: Config Initialization

Deepy SHALL provide non-interactive and interactive configuration commands.

#### Scenario: User initializes config

- **WHEN** a user runs `deepy config init`
- **THEN** Deepy SHALL support `--api-key`, `--provider`, `--model`,
  `--base-url`, `--theme`, and `--force`
- **AND** written config files SHALL use permission mode `0600`
- **AND** the written TOML SHALL include `ui.theme`
- **AND** the written TOML SHALL include `model.provider` when a provider is selected or inferred

#### Scenario: User runs setup

- **WHEN** a user runs `deepy config setup`
- **THEN** Deepy SHALL offer provider choices `DeepSeek`, `OpenRouter`, and `Xiaomi`
- **AND** `DeepSeek` SHALL be the default provider
- **AND** it SHALL collect the API key through password-style input
- **AND** it SHALL offer only models supported by the selected provider
- **AND** when provider is `OpenRouter`, it SHALL also allow the user to paste
  a custom model name copied from the OpenRouter model page
- **AND** it SHALL use the selected provider's default base URL unless the user overrides it
- **AND** it SHALL offer provider-appropriate thinking choices
- **AND** it SHALL show numbered `auto`, `dark`, and `light` UI theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL write TOML with permission mode `0600`
- **AND** the written TOML SHALL include `ui.theme`

#### Scenario: Setup or reset is interrupted

- **WHEN** a user exits or the prompt stream ends during `deepy config setup` or
  `deepy config reset`
- **THEN** Deepy SHALL exit the configuration flow without printing a traceback
- **AND** if a config file existed before the flow, Deepy SHALL preserve or
  restore that file unchanged
- **AND** if no config file existed before the flow, Deepy SHALL leave no
  partial config file behind

### Requirement: DeepSeek Model Configuration
Deepy SHALL persist and validate the active model for the resolved provider in
TOML configuration.

#### Scenario: Default model is loaded
- **WHEN** Deepy loads config with no model name and no explicit provider
- **THEN** Deepy SHALL use provider `deepseek`
- **AND** it SHALL use `deepseek-v4-pro` as the active model

#### Scenario: Supported DeepSeek model is loaded
- **WHEN** Deepy loads config with provider `deepseek`
- **AND** `model.name` is `deepseek-v4-pro` or `deepseek-v4-flash`
- **THEN** Deepy SHALL use the configured model as the active model

#### Scenario: Supported OpenRouter model is loaded
- **WHEN** Deepy loads config with provider `openrouter`
- **AND** `model.name` is `xiaomi/mimo-v2.5-pro` or `xiaomi/mimo-v2.5`
- **THEN** Deepy SHALL use the configured model as the active model

#### Scenario: Custom OpenRouter model is loaded
- **WHEN** Deepy loads config with provider `openrouter`
- **AND** `model.name` is a non-empty model id copied from OpenRouter
- **THEN** Deepy SHALL preserve the configured model as the active model
- **AND** Deepy SHALL treat correctness of that model id as the user's responsibility

#### Scenario: Supported Xiaomi model is loaded
- **WHEN** Deepy loads config with provider `xiaomi`
- **AND** `model.name` is `mimo-v2.5-pro` or `mimo-v2.5`
- **THEN** Deepy SHALL use the configured model as the active model

#### Scenario: Invalid model is selected through Deepy commands
- **WHEN** a user attempts to select a model that is not in the selected provider's model catalog
- **THEN** Deepy SHALL reject the value with a concise usage message
- **AND** it SHALL NOT change the saved config

### Requirement: Reasoning Mode Configuration
Deepy SHALL expose provider-appropriate thinking behavior while persisting
through existing TOML fields.

#### Scenario: DeepSeek reasoning mode none is loaded
- **WHEN** Deepy loads config for provider `deepseek` whose resolved reasoning mode is `none`
- **THEN** Deepy SHALL treat thinking as disabled

#### Scenario: DeepSeek reasoning mode high is loaded
- **WHEN** Deepy loads config for provider `deepseek` whose resolved reasoning mode is `high`
- **THEN** Deepy SHALL treat thinking as enabled
- **AND** it SHALL use `high` as the reasoning effort

#### Scenario: DeepSeek reasoning mode max is loaded
- **WHEN** Deepy loads config for provider `deepseek` whose resolved reasoning mode is `max`
- **THEN** Deepy SHALL treat thinking as enabled
- **AND** it SHALL use `max` as the reasoning effort

#### Scenario: Xiaomi switch-only thinking enabled is loaded
- **WHEN** Deepy loads config for provider `xiaomi`
- **AND** `model.thinking` resolves to true
- **THEN** Deepy SHALL expose thinking mode `enabled`
- **AND** it SHALL normalize the persisted reasoning effort to `enabled` when saving

#### Scenario: Xiaomi switch-only thinking disabled is loaded
- **WHEN** Deepy loads config for provider `xiaomi`
- **AND** `model.thinking` resolves to false
- **THEN** Deepy SHALL expose thinking mode `disabled`
- **AND** it SHALL normalize the persisted reasoning effort to `none` when saving

#### Scenario: OpenRouter boolean reasoning is loaded
- **WHEN** Deepy loads config for provider `openrouter`
- **AND** `model.thinking` resolves to true
- **AND** `model.reasoning_effort` is `enabled`
- **THEN** Deepy SHALL expose thinking mode `enabled`

#### Scenario: OpenRouter effort reasoning is loaded
- **WHEN** Deepy loads config for provider `openrouter`
- **AND** `model.reasoning_effort` is `xhigh`, `high`, `medium`, `low`, or `minimal`
- **THEN** Deepy SHALL expose that effort as the thinking mode

#### Scenario: Legacy thinking fields are loaded
- **WHEN** Deepy loads config that uses `model.thinking` and `model.reasoning_effort`
- **THEN** Deepy SHALL resolve `thinking = false` to disabled thinking
- **AND** it SHALL resolve `thinking = true` with `reasoning_effort = "high"` to enabled thinking
- **AND** it SHALL resolve `thinking = true` with `reasoning_effort = "max"` to DeepSeek reasoning mode `max` only for DeepSeek-style behavior

#### Scenario: Missing thinking fields are loaded
- **WHEN** Deepy loads config with no explicit thinking setting
- **THEN** Deepy SHALL use provider-specific default thinking
- **AND** DeepSeek SHALL default to reasoning mode `max`
- **AND** OpenRouter and Xiaomi MiMo SHALL default to thinking `enabled`

#### Scenario: Reasoning mode is saved
- **WHEN** Deepy saves DeepSeek reasoning mode `none`, `high`, or `max`
- **THEN** Deepy SHALL update existing `model.thinking` and `model.reasoning_effort` fields instead of requiring a new TOML field

#### Scenario: OpenRouter thinking mode is saved
- **WHEN** Deepy saves OpenRouter thinking mode `enabled`
- **THEN** it SHALL write `thinking = true` and `reasoning_effort = "enabled"`
- **WHEN** Deepy saves OpenRouter thinking mode `xhigh`, `high`, `medium`, `low`, or `minimal`
- **THEN** it SHALL write `thinking = true` and the selected effort to `reasoning_effort`
- **WHEN** Deepy saves OpenRouter thinking mode `disabled` or `none`
- **THEN** it SHALL write `thinking = false` and `reasoning_effort = "none"`

#### Scenario: Xiaomi switch-only thinking mode is saved
- **WHEN** Deepy saves Xiaomi MiMo thinking mode `enabled` or `disabled`
- **THEN** it SHALL write `thinking = true` and `reasoning_effort = "enabled"` for `enabled`
- **AND** it SHALL write `thinking = false` and `reasoning_effort = "none"` for `disabled`

### Requirement: Targeted Model Config Updates
Deepy SHALL update provider and model-related TOML settings without discarding
unrelated configuration.

#### Scenario: User saves model settings
- **WHEN** a user changes provider, model, or thinking mode through Deepy commands
- **THEN** Deepy SHALL persist the selected model settings to TOML
- **AND** it SHALL use existing `[model]` fields for provider, model name, base URL, thinking enabled state, and reasoning effort
- **AND** it SHALL preserve existing API key, context, logging, notify, tools, and UI theme settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: Provider changes without explicit model
- **WHEN** a user changes provider without selecting a model
- **THEN** Deepy SHALL select that provider's default model
- **AND** it SHALL select that provider's default thinking mode
- **AND** it SHALL update the base URL to the provider default unless the user has explicitly overridden it in the same operation

#### Scenario: Config path is unknown
- **WHEN** a user attempts to save model settings and Deepy does not know the config path
- **THEN** Deepy SHALL report that the setting cannot be persisted
- **AND** it SHALL keep the current in-memory settings unchanged
