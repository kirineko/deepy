## ADDED Requirements

### Requirement: Input Suggestion Provider Settings
Deepy SHALL construct input suggestion model calls as fixed DeepSeek V4 Flash
non-thinking background requests.

#### Scenario: Input suggestion provider is created
- **WHEN** Deepy creates provider settings for an input suggestion request
- **THEN** it SHALL use model `deepseek-v4-flash`
- **AND** it SHALL disable DeepSeek thinking
- **AND** it SHALL NOT send `reasoning_effort`
- **AND** it SHALL request usage metadata
- **AND** it SHALL disable provider-side storage

#### Scenario: Main reasoning mode is enabled
- **WHEN** the active conversation model uses reasoning mode `high` or `max`
- **THEN** input suggestion requests SHALL still disable DeepSeek thinking
- **AND** they SHALL NOT inherit the active reasoning effort

#### Scenario: Main model is changed
- **WHEN** the active conversation model is changed to any supported DeepSeek
  model
- **THEN** input suggestion requests SHALL continue to use
  `deepseek-v4-flash`
