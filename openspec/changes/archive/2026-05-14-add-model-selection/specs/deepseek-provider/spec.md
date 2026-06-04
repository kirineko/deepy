## ADDED Requirements

### Requirement: Reasoning Mode Provider Mapping
Deepy SHALL map the configured reasoning mode to DeepSeek's OpenAI-compatible
thinking request parameters through the shared model settings builder.

#### Scenario: Reasoning mode none is used
- **WHEN** Deepy builds model settings with reasoning mode `none`
- **THEN** `ModelSettings` SHALL disable DeepSeek thinking
- **AND** it SHALL NOT send `reasoning_effort`

#### Scenario: Reasoning mode high is used
- **WHEN** Deepy builds model settings with reasoning mode `high`
- **THEN** `ModelSettings` SHALL enable DeepSeek thinking
- **AND** it SHALL send `reasoning_effort` as `high`

#### Scenario: Reasoning mode max is used
- **WHEN** Deepy builds model settings with reasoning mode `max`
- **THEN** `ModelSettings` SHALL enable DeepSeek thinking
- **AND** it SHALL send `reasoning_effort` as `max`

### Requirement: Selected Model Provider Construction
Deepy SHALL construct the provider with the active configured model.

#### Scenario: Provider is created after model selection
- **WHEN** Deepy creates a DeepSeek provider after the active model has been changed
- **THEN** it SHALL pass the selected model name to `OpenAIChatCompletionsModel`
- **AND** subsequent model requests SHALL use that selected model
