## ADDED Requirements

### Requirement: Third-Party Provider Model Settings
Deepy SHALL build OpenAI-compatible model settings according to the resolved
provider.

#### Scenario: OpenRouter reasoning effort is configured
- **WHEN** Deepy builds model settings for provider `openrouter`
- **AND** the active model is any configured OpenRouter model id
- **AND** thinking mode is `xhigh`, `high`, `medium`, `low`, or `minimal`
- **THEN** `ModelSettings` SHALL send
  `extra_body={"reasoning": {"enabled": true, "effort": "<selected effort>"}}`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: OpenRouter boolean reasoning is enabled
- **WHEN** Deepy builds model settings for provider `openrouter`
- **AND** the active model is any configured OpenRouter model id
- **AND** thinking mode is `enabled`
- **THEN** `ModelSettings` SHALL send
  `extra_body={"reasoning": {"enabled": true}}`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: OpenRouter reasoning is disabled
- **WHEN** Deepy builds model settings for provider `openrouter`
- **AND** the active model is any configured OpenRouter model id
- **AND** thinking mode is `none` or `disabled`
- **THEN** `ModelSettings` SHALL send
  `extra_body={"reasoning": {"enabled": false}}`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: Xiaomi MiMo thinking is enabled
- **WHEN** Deepy builds model settings for provider `xiaomi`
- **AND** the active model is `mimo-v2.5-pro` or `mimo-v2.5`
- **AND** thinking mode is `enabled`
- **THEN** `ModelSettings` SHALL send `extra_body={"thinking": {"type": "enabled"}}`
- **AND** it SHALL NOT send `reasoning_effort`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: Xiaomi MiMo thinking is disabled
- **WHEN** Deepy builds model settings for provider `xiaomi`
- **AND** the active model is `mimo-v2.5-pro` or `mimo-v2.5`
- **AND** thinking mode is `disabled`
- **THEN** `ModelSettings` SHALL send `extra_body={"thinking": {"type": "disabled"}}`
- **AND** it SHALL NOT send `reasoning_effort`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

### Requirement: Provider-Specific Balance Boundaries
Deepy SHALL keep DeepSeek balance lookup behavior scoped to official DeepSeek
API hosts.

#### Scenario: Third-party provider status is rendered
- **WHEN** Deepy renders status, startup, footer, or session-cost information for provider `openrouter` or `xiaomi`
- **THEN** it SHALL show provider and model identity
- **AND** it SHALL NOT request DeepSeek balance
- **AND** it SHALL NOT present DeepSeek balance as available for that provider

## MODIFIED Requirements

### Requirement: OpenAI Agents SDK Provider

Deepy SHALL construct OpenAI-compatible model access through the OpenAI Agents
SDK `OpenAIChatCompletionsModel`.

#### Scenario: Provider is created

- **WHEN** Deepy creates a model provider
- **THEN** it SHALL use `AsyncOpenAI(base_url, api_key)`
- **AND** it SHALL use `OpenAIChatCompletionsModel`
- **AND** it SHALL pass the selected provider's model id to the model wrapper
- **AND** it SHALL disable tracing of sensitive model data by default

### Requirement: Shared Model Settings

Deepy SHALL reuse one provider/model-settings construction path for ordinary
runs, interactive runs, and live doctor checks.

#### Scenario: Different commands run model calls

- **WHEN** `deepy run`, interactive mode, or `deepy doctor --live` invokes the model
- **THEN** each command SHALL use the same OpenAI-compatible provider and model settings
  builder
- **AND** the builder SHALL map thinking parameters according to the resolved provider

### Requirement: Reasoning Mode Provider Mapping
Deepy SHALL map the configured thinking choice to provider-specific
OpenAI-compatible request parameters through the shared model settings builder.

#### Scenario: DeepSeek reasoning mode none is used
- **WHEN** Deepy builds model settings for provider `deepseek` with reasoning mode `none`
- **THEN** `ModelSettings` SHALL disable DeepSeek thinking
- **AND** it SHALL NOT send `reasoning_effort`

#### Scenario: DeepSeek reasoning mode high is used
- **WHEN** Deepy builds model settings for provider `deepseek` with reasoning mode `high`
- **THEN** `ModelSettings` SHALL enable DeepSeek thinking
- **AND** it SHALL send `reasoning_effort` as `high`

#### Scenario: DeepSeek reasoning mode max is used
- **WHEN** Deepy builds model settings for provider `deepseek` with reasoning mode `max`
- **THEN** `ModelSettings` SHALL enable DeepSeek thinking
- **AND** it SHALL send `reasoning_effort` as `max`

#### Scenario: Provider mapping is centralized
- **WHEN** any runtime path builds model settings for the active conversation model
- **THEN** it SHALL use the shared provider-aware model settings builder
- **AND** UI code SHALL NOT construct provider-specific thinking payloads directly

### Requirement: Selected Model Provider Construction
Deepy SHALL construct the provider with the active configured provider and
model.

#### Scenario: Provider is created after model selection
- **WHEN** Deepy creates an OpenAI-compatible provider after the active provider or model has been changed
- **THEN** it SHALL pass the selected model name to `OpenAIChatCompletionsModel`
- **AND** it SHALL pass the selected provider's resolved base URL to `AsyncOpenAI`
- **AND** subsequent model requests SHALL use that selected provider and model
