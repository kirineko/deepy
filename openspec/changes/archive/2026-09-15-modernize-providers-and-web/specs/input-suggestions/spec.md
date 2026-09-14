## MODIFIED Requirements

### Requirement: Input Suggestion Model
Deepy SHALL use a fixed provider-local Responses model for suggestions without exposing custom suggestion model configuration.

#### Scenario: Suggestion model call is created
- **WHEN** a suggestion request is created
- **THEN** Deepy SHALL use DeepSeek deepseek-flash with none, MiMo mimo-v2.5 with disabled, Kimi kimi-k3 with low, or CLI Proxy gpt-5.6-luna with none according to the active provider
- **AND** it SHALL use that provider credentials, request usage and disable storage

#### Scenario: Active model is changed
- **WHEN** the main model or reasoning changes within a provider
- **THEN** the suggestion model and reasoning SHALL remain fixed for that provider

#### Scenario: Provider changed
- **WHEN** the active provider changes
- **THEN** subsequent suggestions SHALL use the new provider fixed model without requiring another provider key

#### Scenario: User requests suggestion model customization
- **WHEN** a user attempts to configure a custom suggestion model
- **THEN** Deepy SHALL reject or ignore that customization and retain the fixed provider-local model

### Requirement: Input Suggestion Usage Accounting
Deepy SHALL account for input suggestion model usage separately from ordinary
model-turn usage.

#### Scenario: Suggestion usage is known
- **WHEN** an input suggestion model call returns token usage
- **THEN** Deepy SHALL record that usage in an input-suggestion-specific usage
  bucket
- **AND** it SHALL NOT merge that usage into the ordinary turn usage footer
- **AND** it SHALL NOT update latest request Context Window usage checkpoints

#### Scenario: Suggestion usage is displayed
- **WHEN** Deepy displays accumulated interactive usage that includes input
  suggestion calls
- **THEN** it SHALL label suggestion usage separately from ordinary model usage
- **AND** it SHALL identify the actual suggestion provider and model
