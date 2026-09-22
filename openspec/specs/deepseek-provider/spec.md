# DeepSeek Provider Specification

## Purpose

Deepy uses the OpenAI Agents SDK Responses API for DeepSeek, MiMo, Kimi and CLI Proxy while preserving provider-specific reasoning, tool continuations, images, usage and recoverable errors.

## Requirements

### Requirement: Shared Model Settings

Deepy SHALL reuse one provider/model-settings construction path for ordinary
runs, interactive runs, and live doctor checks.

#### Scenario: Different commands run model calls

- **WHEN** `deepy run`, interactive mode, or `deepy doctor --live` invokes the model
- **THEN** each command SHALL use the same OpenAI-compatible provider and model settings
  builder
- **AND** the builder SHALL map thinking parameters according to the resolved provider

### Requirement: DeepSeek Thinking
Deepy SHALL enable DeepSeek Flash reasoning by default through Responses settings.

#### Scenario: Model settings are built
- **WHEN** DeepSeek model settings are built without a reasoning override
- **THEN** Deepy SHALL use `reasoning.effort=max`, request usage, and disable provider-side storage

### Requirement: DeepSeek API Errors

Deepy SHALL return DeepSeek API error information as user-visible assistant
content instead of crashing the terminal process.

#### Scenario: DeepSeek returns an API status error

- **WHEN** the DeepSeek API returns a documented error status
- **THEN** Deepy SHALL format the status, provider message, and actionable hint
  into the model turn output
- **AND** the interactive session SHALL continue instead of printing an uncaught
  traceback

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

### Requirement: Thinking Language Guidance

Deepy SHALL guide DeepSeek to match visible thinking language to the user's
latest natural language when thinking is enabled.

#### Scenario: User asks in Chinese

- **WHEN** the user's latest natural-language request is primarily Chinese
- **AND** DeepSeek thinking is enabled
- **THEN** Deepy's model prompt SHALL instruct DeepSeek to use Chinese for
  visible thinking unless the user requested another language

#### Scenario: User asks in another language

- **WHEN** the user's latest natural-language request is primarily not Chinese
- **AND** DeepSeek thinking is enabled
- **THEN** Deepy's model prompt SHALL instruct DeepSeek to match that language
  for visible thinking unless the user requested another language

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

### Requirement: On-Demand DeepSeek Balance Lookup
Deepy SHALL support read-only DeepSeek account balance lookups for explicit
user-visible status and session-cost surfaces.

#### Scenario: Status command requests balance
- **WHEN** the user runs `/status`
- **AND** a DeepSeek API key is configured
- **AND** the configured API base URL resolves to an official DeepSeek API host
- **THEN** Deepy SHALL request `GET /user/balance`
- **AND** it SHALL authenticate with `Authorization: Bearer <api_key>`
- **AND** it SHALL use a short timeout suitable for an interactive status command

#### Scenario: Session cost snapshot requests balance
- **WHEN** Deepy records a start or end balance snapshot for an interactive
  session cost summary
- **AND** a DeepSeek API key is configured
- **AND** the configured API base URL resolves to an official DeepSeek API host
- **THEN** Deepy SHALL request `GET /user/balance`
- **AND** it SHALL authenticate with `Authorization: Bearer <api_key>`
- **AND** it SHALL use a short timeout suitable for interactive shutdown paths

#### Scenario: Balance response is valid
- **WHEN** Deepy receives a valid balance response
- **THEN** it SHALL parse `is_available`
- **AND** it SHALL parse each `balance_infos` entry's `currency`,
  `total_balance`, `granted_balance`, and `topped_up_balance`
- **AND** it SHALL expose those parsed values to status and session-cost
  renderers

#### Scenario: Balance lookup is unavailable
- **WHEN** the API key is missing, the configured base URL is not an official
  DeepSeek API host, the request times out, the provider returns an error
  status, or the response cannot be parsed
- **THEN** Deepy SHALL return a balance unavailable result
- **AND** it SHALL include a concise reason suitable for display
- **AND** it SHALL NOT raise an uncaught exception into the interactive UI

#### Scenario: Non-balance paths run
- **WHEN** Deepy starts up, renders a welcome panel, renders a footer or status
  bar, runs `deepy doctor`, runs a model turn, records usage, prepares input
  suggestions, renders usage after a turn, or renders normal model-turn output
- **THEN** Deepy SHALL NOT request `GET /user/balance`
- **AND** it SHALL NOT perform any other DeepSeek balance network call

#### Scenario: Secrets are displayed
- **WHEN** Deepy renders balance, cost, or status information
- **THEN** it SHALL NOT print the configured API key
- **AND** it SHALL NOT include the API key in error text

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

### Requirement: DeepSeek Cache Prefix Snapshot
Deepy SHALL compute a deterministic cache-prefix snapshot for DeepSeek model
requests before invoking the OpenAI Agents SDK.

#### Scenario: DeepSeek model request is prepared
- **WHEN** Deepy prepares a model request for provider `deepseek`
- **THEN** it SHALL compute a cache-prefix snapshot from the stable request
  components Deepy controls
- **AND** the snapshot SHALL include system instructions, ordered built-in tool
  schemas including the v3 `Read`, `Write`, and `Update` definitions, ordered
  MCP tool schemas, model id, DeepSeek reasoning settings, model settings that
  affect request shape, and stable skill/rule/prompt blocks
- **AND** Deepy SHALL persist the snapshot fingerprint with the active session
  metadata

#### Scenario: Stable prefix is unchanged
- **WHEN** two consecutive DeepSeek turns use identical cache-prefix snapshot
  components
- **THEN** Deepy SHALL reuse the same cache-prefix fingerprint
- **AND** it SHALL NOT record a prefix-change cache break for the second turn

#### Scenario: Prefix component changes
- **WHEN** any cache-prefix snapshot component changes between DeepSeek turns
- **THEN** Deepy SHALL compute a different cache-prefix fingerprint
- **AND** it SHALL record a cache break reason that identifies the changed
  component category

#### Scenario: File tool surface changes
- **WHEN** Deepy upgrades from the v2 file tool surface to the v3 `Read`,
  `Write`, and `Update` surface
- **THEN** Deepy SHALL treat the changed built-in tool schema set as an
  intentional prefix change
- **AND** subsequent unchanged turns SHALL reuse the new v3 prefix snapshot

### Requirement: DeepSeek SDK Request Shape Diagnostics
Deepy SHALL provide a diagnostic path for validating cache-prefix assumptions
against the request shape produced through the OpenAI Agents SDK.

#### Scenario: Diagnostic capture is enabled in tests
- **WHEN** provider request-shape diagnostics are enabled by tests or explicit
  developer tooling
- **THEN** Deepy SHALL expose the canonical cache-prefix snapshot and the SDK
  request-shape fields needed to compare prefix ordering
- **AND** it SHALL omit API keys, authorization headers, and secret-bearing
  values from captured diagnostics

#### Scenario: Normal user session runs
- **WHEN** a normal Deepy session sends a provider request
- **THEN** Deepy SHALL NOT log full provider payloads by default
- **AND** it SHALL NOT print or persist API keys

### Requirement: DeepSeek Cache-Aligned Auxiliary Folding
Deepy SHALL keep context folding and compaction auxiliary requests aligned with
the active DeepSeek conversation model and model settings.

#### Scenario: DeepSeek compaction summary is requested
- **WHEN** Deepy creates a summary or fold request for a DeepSeek session
- **THEN** it SHALL use the active conversation DeepSeek model
- **AND** it SHALL use the active conversation DeepSeek model settings
- **AND** it SHALL request usage metadata through those model settings
- **AND** it SHALL preserve provider-side storage disabling through those model
  settings

#### Scenario: Active conversation uses reasoning
- **WHEN** the active DeepSeek conversation uses reasoning mode `high` or `max`
- **AND** Deepy creates a compaction summary request
- **THEN** the summary request SHALL keep the active DeepSeek reasoning setting
- **AND** it SHALL NOT switch to a separate auxiliary model

#### Scenario: Non-DeepSeek provider compacts context
- **WHEN** Deepy creates a summary or fold request for a provider other than
  official DeepSeek
- **THEN** it SHALL use provider-safe compaction settings
- **AND** it SHALL NOT assume DeepSeek cache behavior is available

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
- **WHEN** Deepy constructs tools for `mimo-v2.6-flash` or `mimo-v2.6-pro` under `mimo`
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
