## MODIFIED Requirements

### Requirement: Provider Selection Configuration
Deepy SHALL support an optional provider selection in TOML model configuration.

#### Scenario: Config has explicit provider
- **WHEN** Deepy loads config with `model.provider` set to `deepseek`, `openrouter`, `xiaomi`, or `localhost`
- **THEN** Deepy SHALL resolve that provider as the active provider
- **AND** it SHALL validate model and thinking choices against that provider's catalog

#### Scenario: Config has no provider and known base URL
- **WHEN** Deepy loads config without `model.provider`
- **AND** `model.base_url` points at official DeepSeek, OpenRouter, Xiaomi MiMo, or loopback localhost hosts
- **THEN** Deepy SHALL infer `deepseek`, `openrouter`, `xiaomi`, or `localhost` respectively

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
- **AND** it SHALL use `http://127.0.0.1:8317/v1` for `localhost`

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

#### Scenario: Localhost effort reasoning is loaded
- **WHEN** Deepy loads config for provider `localhost`
- **AND** `model.reasoning_effort` is `none`, `low`, `medium`, `high`, or `xhigh`
- **THEN** Deepy SHALL expose that effort as the thinking mode
- **AND** it SHALL treat `none` as disabled thinking
- **AND** it SHALL treat the other efforts as enabled thinking

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
- **AND** localhost SHALL default to reasoning mode `medium`

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

#### Scenario: Localhost thinking mode is saved
- **WHEN** Deepy saves localhost thinking mode `low`, `medium`, `high`, or `xhigh`
- **THEN** it SHALL write `thinking = true` and the selected effort to `reasoning_effort`
- **WHEN** Deepy saves localhost thinking mode `none`
- **THEN** it SHALL write `thinking = false` and `reasoning_effort = "none"`

### Requirement: Image Input Model Capability Metadata
Deepy SHALL expose image-input support as explicit model capability metadata.

#### Scenario: Xiaomi MiMo image-capable models are loaded
- **WHEN** Deepy builds the Xiaomi model catalog
- **THEN** `mimo-v2.5` SHALL be marked as supporting image input
- **AND** `mimo-v2.5-pro` SHALL be marked as not supporting image input

#### Scenario: OpenRouter MiMo image-capable models are loaded
- **WHEN** Deepy builds the OpenRouter model catalog
- **THEN** `xiaomi/mimo-v2.5` SHALL be marked as supporting image input
- **AND** `xiaomi/mimo-v2.5-pro` SHALL be marked as not supporting image input

#### Scenario: Localhost GPT-5.6 image-capable models are loaded
- **WHEN** Deepy builds the localhost model catalog
- **THEN** `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` SHALL be marked as supporting image input

#### Scenario: DeepSeek models are loaded
- **WHEN** Deepy builds the DeepSeek model catalog
- **THEN** DeepSeek models SHALL be marked as not supporting image input

#### Scenario: Custom OpenRouter model is configured
- **WHEN** Deepy loads a custom OpenRouter model id that is not one of the curated MiMo image-capable model ids
- **THEN** Deepy SHALL treat image input as unsupported for that model
- **AND** it SHALL preserve the custom model id behavior for text-only use

#### Scenario: Future Kimi capability is added
- **WHEN** a future change adds Kimi K2.6 as a supported model
- **THEN** Deepy SHALL be able to mark image support through the same capability metadata
- **AND** it SHALL NOT require a new prompt attachment model
