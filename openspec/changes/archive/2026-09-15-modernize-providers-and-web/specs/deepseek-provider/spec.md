## MODIFIED Requirements

### Requirement: DeepSeek Thinking
Deepy SHALL enable DeepSeek Flash reasoning by default through Responses settings.

#### Scenario: Model settings are built
- **WHEN** DeepSeek model settings are built without a reasoning override
- **THEN** Deepy SHALL use `reasoning.effort=max`, request usage, and disable provider-side storage

### Requirement: Reasoning Mode Provider Mapping
Deepy SHALL map reasoning modes to provider-supported Responses parameters centrally.

#### Scenario: DeepSeek reasoning mode none is used
- **WHEN** the selected DeepSeek mode is none, high or max
- **THEN** Deepy SHALL send the corresponding Responses reasoning effort and omit Chat Completions thinking fields

#### Scenario: MiMo mapping
- **WHEN** MiMo thinking is disabled or enabled
- **THEN** Deepy SHALL map disabled to Responses `reasoning.effort=none` and enabled to `high`
- **AND** it SHALL NOT advertise low/medium/high as distinct MiMo reasoning strengths

#### Scenario: Kimi mapping
- **WHEN** Kimi reasoning is low, high or max
- **THEN** Deepy SHALL send the corresponding Responses effort and provider-supported tool-choice/options
- **AND** it SHALL NOT send unsupported forced tool choices or disabled-thinking settings

#### Scenario: CLI mapping
- **WHEN** CLI Proxy model settings are built
- **THEN** Deepy SHALL send only the selected model supported Responses reasoning/options

#### Scenario: Provider mapping is centralized
- **WHEN** any runtime path constructs model settings
- **THEN** it SHALL use shared provider-aware mapping and SHALL NOT construct provider payloads in UI code

#### Scenario: DeepSeek reasoning mode high is used
- **WHEN** DeepSeek reasoning is high
- **THEN** Deepy SHALL send Responses reasoning.effort=high

#### Scenario: DeepSeek reasoning mode max is used
- **WHEN** DeepSeek reasoning is max
- **THEN** Deepy SHALL send Responses reasoning.effort=max

### Requirement: Selected Model Provider Construction
Deepy SHALL construct the provider from the active profile without leaking a previous provider settings.

#### Scenario: Provider is created after model selection
- **WHEN** the active provider or model changes
- **THEN** subsequent requests SHALL use the selected Responses model, base URL, resolved credentials and supported reasoning settings
- **AND** provider-specific opaque history items SHALL NOT be forwarded unchanged to another provider

### Requirement: Input Suggestion Provider Settings
Deepy SHALL build provider-local fixed input suggestion requests through Responses.

#### Scenario: Input suggestion provider is created
- **WHEN** an input suggestion is generated
- **THEN** Deepy SHALL use `deepseek-flash/none`, `mimo-v2.5/disabled`, `kimi-k3/low`, or `gpt-5.6-luna/none` for the respective active provider
- **AND** it SHALL request usage, disable provider-side storage, and use only the active provider credentials
- **AND** it SHALL NOT inherit the main reasoning mode or require a separate provider key

#### Scenario: Main reasoning mode is enabled
- **WHEN** main conversation reasoning is enabled
- **THEN** suggestions SHALL retain the fixed provider-local reasoning rather than inherit main reasoning

#### Scenario: Main model is changed
- **WHEN** the main model changes within the same provider
- **THEN** suggestions SHALL retain that provider's fixed suggestion model

### Requirement: Provider-Specific Balance Boundaries
Deepy SHALL keep DeepSeek balance lookup behavior scoped to official DeepSeek
API hosts.

#### Scenario: Third-party provider status is rendered
- **WHEN** Deepy renders status, startup, footer, or session-cost information for provider `mimo`, `kimi`, or `cli_proxy`
- **THEN** it SHALL show provider and model identity
- **AND** it SHALL NOT request DeepSeek balance
- **AND** it SHALL NOT present DeepSeek balance as available for that provider

#### Scenario: Non-DeepSeek conversation uses built-in search
- **WHEN** a non-DeepSeek conversation calls the DeepSeek search service
- **THEN** Deepy SHALL NOT present DeepSeek balance as the active conversation provider balance

## ADDED Requirements

### Requirement: Responses Tool History And Streaming
Deepy SHALL preserve executable tool continuations and observable streaming behavior across supported Responses providers.

#### Scenario: Function continuation
- **WHEN** a provider emits a function call and Deepy produces a result
- **THEN** the next request SHALL contain the corresponding function output and correct call ID
- **AND** required provider reasoning items SHALL be retained in a supported Responses form
- **AND** the model SHALL be able to complete the second round

#### Scenario: Streaming turn
- **WHEN** a Responses stream emits text, reasoning, tool events and final usage
- **THEN** Deepy SHALL normalize them into the existing transcript/tool lifecycle
- **AND** final usage SHALL be recorded once and the completed response SHALL remain replayable

#### Scenario: Failure or cancellation
- **WHEN** the stream fails, is incomplete, or the user cancels
- **THEN** Deepy SHALL leave the UI usable, expose a recoverable outcome and retain valid history
- **AND** it SHALL NOT invent a completed assistant response or unknown usage

#### Scenario: Storage disabled
- **WHEN** Deepy continues a conversation or resumes a session
- **THEN** it SHALL reconstruct valid local history without requiring provider-side stored responses

### Requirement: Unified Responses Provider Access
Deepy SHALL use Responses API for all supported conversation providers while preserving SDK tool execution and sensitive tracing defaults.

#### Scenario: Provider creation
- **WHEN** Deepy constructs a supported provider
- **THEN** it SHALL use the selected model, that provider resolved key and base URL for Responses requests
- **AND** sensitive model-data tracing SHALL remain disabled by default

#### Scenario: All model paths
- **WHEN** a main turn, subagent, input suggestion, compaction, summary, or live doctor invokes a model
- **THEN** it SHALL use the shared provider-aware Responses construction path
- **AND** it SHALL NOT fall back to Chat Completions
- **AND** only the separate built-in WebSearch service SHALL use Anthropic Messages

### Requirement: MiMo Responses Tool Compatibility
Deepy SHALL scope MiMo tool-schema compatibility to supported direct MiMo models while preserving normal function-call execution.

#### Scenario: MiMo Responses tool call
- **WHEN** Deepy constructs tools for `mimo-v2.5` or `mimo-v2.5-pro` under `mimo`
- **THEN** it SHALL use compatible model-visible schemas and preserve runtime defaults
- **AND** calls SHALL execute through Responses function_call/function_call_output with matching call IDs

#### Scenario: Other provider
- **WHEN** the provider is not MiMo
- **THEN** Deepy SHALL NOT apply MiMo-specific schema transformations

#### Scenario: Pseudo call
- **WHEN** assistant prose resembles XML or another textual tool-call syntax
- **THEN** Deepy SHALL treat it as text and SHALL NOT execute it

### Requirement: Responses Image Content Normalization
Deepy SHALL normalize supported prompt and tool images into Responses input content.

#### Scenario: Image content
- **WHEN** supported model input includes images
- **THEN** Deepy SHALL send `input_image` with a base64 data URL preserving MIME type and order
- **AND** prompt text SHALL use `input_text` before the images
- **AND** Kimi SHALL NOT receive remote HTTP image URLs

#### Scenario: Image-only content
- **WHEN** supported input contains images without text
- **THEN** Deepy SHALL prepend concise image-description guidance without requesting tool execution or file mutation

#### Scenario: Text-only content
- **WHEN** input contains no images
- **THEN** Deepy SHALL preserve valid text-only Responses input without artificial image blocks

## REMOVED Requirements

### Requirement: Third-Party Provider Model Settings
**Reason**: The old Chat Completions, removed-provider, or provider-specific duplicate contract is superseded.
**Migration**: Use the supported provider catalog, shared Responses reasoning/history/image contracts and provider-local suggestion settings; no legacy compatibility path is retained.

### Requirement: Xiaomi MiMo Reasoning Content Replay
**Reason**: The old Chat Completions, removed-provider, or provider-specific duplicate contract is superseded.
**Migration**: Use the supported provider catalog, shared Responses reasoning/history/image contracts and provider-local suggestion settings; no legacy compatibility path is retained.

### Requirement: OpenRouter Reasoning Alias Replay
**Reason**: The old Chat Completions, removed-provider, or provider-specific duplicate contract is superseded.
**Migration**: Use the supported provider catalog, shared Responses reasoning/history/image contracts and provider-local suggestion settings; no legacy compatibility path is retained.

### Requirement: MiMo Image Input Request Serialization
**Reason**: The old Chat Completions, removed-provider, or provider-specific duplicate contract is superseded.
**Migration**: Use the supported provider catalog, shared Responses reasoning/history/image contracts and provider-local suggestion settings; no legacy compatibility path is retained.

### Requirement: Localhost Responses Provider Model Settings
**Reason**: The old Chat Completions, removed-provider, or provider-specific duplicate contract is superseded.
**Migration**: Use the supported provider catalog, shared Responses reasoning/history/image contracts and provider-local suggestion settings; no legacy compatibility path is retained.

### Requirement: Localhost Input Suggestion Provider Settings
**Reason**: The old Chat Completions, removed-provider, or provider-specific duplicate contract is superseded.
**Migration**: Use the supported provider catalog, shared Responses reasoning/history/image contracts and provider-local suggestion settings; no legacy compatibility path is retained.

### Requirement: OpenAI Agents SDK Provider
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "Unified Responses Provider Access" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.

### Requirement: MiMo Tool Schema Compatibility Boundary
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "MiMo Responses Tool Compatibility" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.

### Requirement: Image Content Block Normalization
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "Responses Image Content Normalization" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.
