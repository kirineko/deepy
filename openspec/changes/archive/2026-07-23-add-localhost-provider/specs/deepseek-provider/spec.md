## ADDED Requirements

### Requirement: Localhost Responses Provider Model Settings
Deepy SHALL build Responses API model settings for provider `localhost`.

#### Scenario: Localhost reasoning effort medium is configured
- **WHEN** Deepy builds model settings for provider `localhost`
- **AND** thinking mode is `medium`
- **THEN** `ModelSettings` SHALL set Responses `reasoning.effort` to `medium`
- **AND** it SHALL NOT send DeepSeek/OpenRouter/Xiaomi chat thinking `extra_body` payloads
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: Localhost reasoning effort none is configured
- **WHEN** Deepy builds model settings for provider `localhost`
- **AND** thinking mode is `none`
- **THEN** `ModelSettings` SHALL set Responses `reasoning.effort` to `none`
- **AND** it SHALL NOT send DeepSeek/OpenRouter/Xiaomi chat thinking `extra_body` payloads

#### Scenario: Localhost reasoning effort xhigh is configured
- **WHEN** Deepy builds model settings for provider `localhost`
- **AND** thinking mode is `xhigh`
- **THEN** `ModelSettings` SHALL set Responses `reasoning.effort` to `xhigh`

### Requirement: Localhost Input Suggestion Provider Settings
Deepy SHALL construct localhost input suggestion model calls as fixed
`gpt-5.6-luna` Chat Completions requests with reasoning effort `none`.

#### Scenario: Localhost input suggestion provider is created
- **WHEN** Deepy creates provider settings for an input suggestion request
- **AND** the active provider is `localhost`
- **THEN** it SHALL use model `gpt-5.6-luna`
- **AND** it SHALL send Chat Completions `reasoning_effort` as `none`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage
- **AND** it SHALL NOT inherit the active conversation model or thinking mode

## MODIFIED Requirements

### Requirement: OpenAI Agents SDK Provider

Deepy SHALL construct OpenAI-compatible model access through the OpenAI Agents
SDK using the provider catalog's API transport.

#### Scenario: Provider is created

- **WHEN** Deepy creates a model provider for a provider whose API transport is
  Chat Completions
- **THEN** it SHALL use `AsyncOpenAI(base_url, api_key)`
- **AND** it SHALL use `OpenAIChatCompletionsModel`
- **AND** it SHALL pass the selected provider's model id to the model wrapper
- **AND** it SHALL disable tracing of sensitive model data by default

#### Scenario: Localhost Responses provider is created

- **WHEN** Deepy creates a model provider for provider `localhost`
- **THEN** it SHALL use `AsyncOpenAI(base_url, api_key)`
- **AND** it SHALL use `OpenAIResponsesModel`
- **AND** it SHALL pass the selected localhost model id to the model wrapper
- **AND** it SHALL disable tracing of sensitive model data by default

### Requirement: Selected Model Provider Construction
Deepy SHALL construct the provider with the active configured provider and
model.

#### Scenario: Provider is created after model selection
- **WHEN** Deepy creates an OpenAI-compatible provider after the active provider or model has been changed
- **THEN** it SHALL pass the selected model name to the provider's model wrapper
  (`OpenAIChatCompletionsModel` or `OpenAIResponsesModel`)
- **AND** it SHALL pass the selected provider's resolved base URL to `AsyncOpenAI`
- **AND** subsequent model requests SHALL use that selected provider and model

### Requirement: Input Suggestion Provider Settings
Deepy SHALL construct input suggestion model calls as fixed DeepSeek V4 Flash
non-thinking background requests when the active provider is DeepSeek.

#### Scenario: Input suggestion provider is created
- **WHEN** Deepy creates provider settings for an input suggestion request
- **AND** the active provider is `deepseek` or unset DeepSeek-style behavior
- **THEN** it SHALL use model `deepseek-v4-flash`
- **AND** it SHALL disable DeepSeek thinking
- **AND** it SHALL NOT send `reasoning_effort`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: Main reasoning mode is enabled
- **WHEN** the active conversation model uses reasoning mode `high` or `max`
- **AND** the active provider is `deepseek`
- **THEN** input suggestion requests SHALL still disable DeepSeek thinking
- **AND** they SHALL NOT inherit the active reasoning effort

#### Scenario: Main model is changed
- **WHEN** the active conversation model is changed to any supported DeepSeek
  model
- **THEN** input suggestion requests SHALL continue to use
  `deepseek-v4-flash`
