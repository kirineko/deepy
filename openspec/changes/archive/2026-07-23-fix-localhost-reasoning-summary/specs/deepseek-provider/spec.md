## MODIFIED Requirements

### Requirement: Localhost Responses Provider Model Settings
Deepy SHALL build Responses API model settings for provider `localhost`.

#### Scenario: Localhost reasoning effort medium is configured
- **WHEN** Deepy builds model settings for provider `localhost`
- **AND** thinking mode is `medium`
- **THEN** `ModelSettings` SHALL set Responses `reasoning.effort` to `medium`
- **AND** it SHALL set Responses `reasoning.summary` to `auto`
- **AND** it SHALL NOT send DeepSeek/OpenRouter/Xiaomi chat thinking `extra_body` payloads
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: Localhost reasoning effort none is configured
- **WHEN** Deepy builds model settings for provider `localhost`
- **AND** thinking mode is `none`
- **THEN** `ModelSettings` SHALL set Responses `reasoning.effort` to `none`
- **AND** it SHALL NOT set Responses `reasoning.summary`
- **AND** it SHALL NOT send DeepSeek/OpenRouter/Xiaomi chat thinking `extra_body` payloads

#### Scenario: Localhost reasoning effort xhigh is configured
- **WHEN** Deepy builds model settings for provider `localhost`
- **AND** thinking mode is `xhigh`
- **THEN** `ModelSettings` SHALL set Responses `reasoning.effort` to `xhigh`
- **AND** it SHALL set Responses `reasoning.summary` to `auto`
