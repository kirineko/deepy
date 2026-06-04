# DeepSeek Provider Specification

## Purpose

Deepy uses the OpenAI Agents SDK with DeepSeek's OpenAI-compatible Chat
Completions API while preserving DeepSeek-specific thinking, usage, and error
behavior.
## Requirements
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

### Requirement: DeepSeek Thinking

Deepy SHALL enable DeepSeek thinking by default for supported DeepSeek models.

#### Scenario: Model settings are built

- **WHEN** Deepy builds model settings for DeepSeek
- **THEN** `thinking` SHALL default to enabled
- **AND** `reasoning_effort` SHALL default to `max`
- **AND** `ModelSettings` SHALL include usage and disable provider-side storage

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

### Requirement: MiMo Tool Schema Compatibility Boundary
Deepy SHALL apply MiMo tool schema compatibility only when the resolved provider
and model identify a Xiaomi MiMo model that requires it.

#### Scenario: Xiaomi official MiMo model is selected
- **WHEN** Deepy constructs an agent for provider `xiaomi`
- **AND** the active model is `mimo-v2.5` or `mimo-v2.5-pro`
- **THEN** Deepy SHALL construct built-in tools using MiMo-compatible
  model-visible schemas
- **AND** model tool calls SHALL continue through the standard OpenAI Agents SDK
  `message.tool_calls` path

#### Scenario: OpenRouter MiMo model is selected
- **WHEN** Deepy constructs an agent for provider `openrouter`
- **AND** the active model id is `xiaomi/mimo-v2.5` or
  `xiaomi/mimo-v2.5-pro`
- **THEN** Deepy SHALL construct built-in tools using MiMo-compatible
  model-visible schemas
- **AND** model tool calls SHALL continue through the standard OpenAI Agents SDK
  `message.tool_calls` path

#### Scenario: OpenRouter non-MiMo model is selected
- **WHEN** Deepy constructs an agent for provider `openrouter`
- **AND** the active model id does not identify Xiaomi MiMo
- **THEN** Deepy SHALL use the existing built-in tool schemas
- **AND** it SHALL NOT apply MiMo-specific schema compatibility

#### Scenario: MiMo returns pseudo tool-call content
- **WHEN** a MiMo model returns assistant content that resembles an XML-like
  `<tool_call>` block instead of standard `message.tool_calls`
- **THEN** Deepy SHALL treat that response as ordinary assistant content
- **AND** it SHALL NOT execute tools by parsing provider-specific pseudo
  tool-call text

### Requirement: Xiaomi MiMo Reasoning Content Replay
Deepy SHALL replay Xiaomi direct MiMo reasoning content when required for
thinking-enabled multi-turn tool calls.

#### Scenario: Xiaomi direct MiMo thinking tool call continues
- **WHEN** Deepy sends a follow-up request to provider `xiaomi`
- **AND** the active model is `mimo-v2.5` or `mimo-v2.5-pro`
- **AND** the previous assistant turn produced `reasoning_content` before a
  standard tool call
- **THEN** Deepy SHALL include that prior `reasoning_content` in the replayed
  assistant message
- **AND** the tool result follow-up SHALL continue through the standard OpenAI
  Chat Completions message format

#### Scenario: OpenRouter MiMo thinking tool call continues
- **WHEN** Deepy sends a follow-up request to provider `openrouter`
- **AND** the active model id is `xiaomi/mimo-v2.5` or
  `xiaomi/mimo-v2.5-pro`
- **THEN** Deepy SHALL NOT add Xiaomi-specific `reasoning_content` replay
- **AND** it SHALL keep using OpenRouter's reasoning request mapping

### Requirement: OpenRouter Reasoning Alias Replay
Deepy SHALL preserve OpenRouter plaintext reasoning across Chat Completions tool
follow-up requests by using the existing reasoning-content replay mechanism.

#### Scenario: OpenRouter response contains plaintext reasoning before a tool call
- **WHEN** Deepy receives a Chat Completions response from provider `openrouter`
- **AND** the assistant message contains a non-empty `reasoning` string
- **AND** the assistant message does not already contain `reasoning_content`
- **AND** the assistant message contains standard OpenAI `tool_calls`
- **THEN** Deepy SHALL make that reasoning available to the existing
  `reasoning_content` replay path
- **AND** it SHALL preserve the standard `tool_calls` message structure

#### Scenario: OpenRouter tool follow-up is replayed
- **WHEN** Deepy sends a tool-result follow-up request to provider `openrouter`
- **AND** the previous assistant turn produced replayable OpenRouter reasoning
  before a standard tool call
- **THEN** Deepy SHALL include the prior reasoning as `reasoning_content` on the
  replayed assistant tool-call message
- **AND** it SHALL continue using OpenRouter's request-side `reasoning` mapping

#### Scenario: OpenRouter response already contains reasoning content
- **WHEN** Deepy receives a Chat Completions response from provider `openrouter`
- **AND** the assistant message already contains `reasoning_content`
- **THEN** Deepy SHALL NOT overwrite that existing `reasoning_content`
- **AND** replay SHALL continue through the existing reasoning-content path

#### Scenario: Non-OpenRouter provider returns reasoning
- **WHEN** Deepy receives or replays reasoning for a provider other than
  `openrouter`, `deepseek`, or direct Xiaomi MiMo
- **THEN** Deepy SHALL NOT enable OpenRouter-specific reasoning alias replay
- **AND** existing DeepSeek and direct Xiaomi reasoning-content behavior SHALL
  remain unchanged

#### Scenario: OpenRouter response contains reasoning details
- **WHEN** Deepy receives `reasoning_details` from OpenRouter
- **THEN** Deepy SHALL NOT synthesize, reorder, or mutate `reasoning_details` as
  part of the reasoning alias replay
- **AND** full `reasoning_details` preservation SHALL remain outside the scope
  of this behavior

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

### Requirement: MiMo Image Input Request Serialization
Deepy SHALL serialize prompt image attachments through the shared OpenAI-compatible provider path only for supported MiMo image models.

#### Scenario: Xiaomi official MiMo image prompt is sent
- **WHEN** Deepy sends a model request for provider `xiaomi`
- **AND** the active model is `mimo-v2.5`
- **AND** the user prompt contains image attachments
- **THEN** Deepy SHALL send a multipart user message with text and image content blocks
- **AND** each image block SHALL contain a base64 data URL with the image MIME type

#### Scenario: OpenRouter MiMo image prompt is sent
- **WHEN** Deepy sends a model request for provider `openrouter`
- **AND** the active model is `xiaomi/mimo-v2.5`
- **AND** the user prompt contains image attachments
- **THEN** Deepy SHALL send a multipart user message with text and image content blocks
- **AND** each image block SHALL contain a base64 data URL with the image MIME type

#### Scenario: DeepSeek image prompt is blocked before request
- **WHEN** Deepy prepares a model request for provider `deepseek`
- **AND** prompt state contains image attachments
- **THEN** Deepy SHALL reject or discard the image attachments before provider serialization
- **AND** it SHALL NOT send image content blocks to DeepSeek

#### Scenario: Text-only prompt is sent
- **WHEN** the user prompt contains no image attachments
- **THEN** Deepy SHALL preserve the existing text-only request shape for all providers

### Requirement: Image Content Block Normalization
Deepy SHALL normalize internal image content blocks to the Chat Completions image-url shape when using the OpenAI-compatible model wrapper.

#### Scenario: SDK image block is prepared for Chat Completions
- **WHEN** model input contains an internal image content block
- **THEN** Deepy SHALL convert it to a Chat Completions `image_url` content part
- **AND** the converted part SHALL preserve the original data URL

#### Scenario: SDK text block is prepared for Chat Completions
- **WHEN** model input contains an internal text content block in the same user message as image content
- **THEN** Deepy SHALL convert it to a Chat Completions `text` content part
- **AND** the text part SHALL remain before image parts when it originated from prompt text

#### Scenario: SDK image-only message is prepared for Chat Completions
- **WHEN** model input contains image content blocks without a non-empty text content block
- **THEN** Deepy SHALL prepend a Chat Completions `text` content part
- **AND** that text SHALL ask the model to describe the image without executing tools or modifying files
- **AND** image content parts SHALL remain after that text part

#### Scenario: Future Kimi path reuses image normalization
- **WHEN** a future provider uses the same OpenAI-compatible image-url contract
- **THEN** Deepy's image normalization SHALL be reusable without changing prompt UI state

