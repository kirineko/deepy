## MODIFIED Requirements

### Requirement: MiMo Responses Tool Compatibility
Deepy SHALL scope MiMo tool-schema compatibility to supported direct MiMo models while preserving normal function-call execution.

#### Scenario: MiMo Responses tool call
- **WHEN** Deepy constructs tools for `mimo-v2.6-flash` or `mimo-v2.6-pro` under `mimo`
- **THEN** it SHALL use compatible model-visible schemas and preserve runtime defaults
- **AND** calls SHALL execute through Responses function_call/function_call_output with matching call IDs

#### Scenario: Other provider
- **WHEN** the provider is not MiMo
- **THEN** Deepy SHALL NOT apply MiMo-specific schema transformations

#### Scenario: Pseudo call
- **WHEN** assistant prose resembles XML or another textual tool-call syntax
- **THEN** Deepy SHALL treat it as text and SHALL NOT execute it

### Requirement: Input Suggestion Provider Settings
Deepy SHALL build provider-local fixed input suggestion requests through Responses.

#### Scenario: Input suggestion provider is created
- **WHEN** an input suggestion is generated
- **THEN** Deepy SHALL use `deepseek-flash/none`, `mimo-v2.6-flash/disabled`, `kimi-k3/low`, or `gpt-5.6-luna/none` for the respective active provider
- **AND** it SHALL request usage, disable provider-side storage, and use only the active provider credentials
- **AND** it SHALL NOT inherit the main reasoning mode or require a separate provider key

#### Scenario: Main reasoning mode is enabled
- **WHEN** main conversation reasoning is enabled
- **THEN** suggestions SHALL retain the fixed provider-local reasoning rather than inherit main reasoning

#### Scenario: Main model is changed
- **WHEN** the main model changes within the same provider
- **THEN** suggestions SHALL retain that provider's fixed suggestion model
