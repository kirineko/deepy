## ADDED Requirements

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
