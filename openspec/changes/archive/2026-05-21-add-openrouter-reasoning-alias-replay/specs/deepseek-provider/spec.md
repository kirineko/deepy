## ADDED Requirements

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
