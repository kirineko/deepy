## MODIFIED Requirements

### Requirement: Input Suggestion Model
Deepy SHALL use a fixed provider-local Responses model for suggestions without exposing custom suggestion model configuration.

#### Scenario: Suggestion model call is created
- **WHEN** a suggestion request is created
- **THEN** Deepy SHALL use DeepSeek deepseek-flash with none, MiMo mimo-v2.6-flash with disabled, Kimi kimi-k3 with low, or CLI Proxy gpt-5.6-luna with none according to the active provider
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
