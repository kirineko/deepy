## MODIFIED Requirements

### Requirement: Supported Image Model Set
Deepy SHALL treat image input as supported only for explicitly allowlisted
image-capable models.

#### Scenario: Xiaomi official MiMo model is active
- **WHEN** the active provider is `xiaomi`
- **AND** the active model is `mimo-v2.5`
- **THEN** Deepy SHALL allow image attachments on user prompts

#### Scenario: Xiaomi official MiMo Pro model is active
- **WHEN** the active provider is `xiaomi`
- **AND** the active model is `mimo-v2.5-pro`
- **THEN** Deepy SHALL treat image attachments as unsupported
- **AND** it SHALL NOT send image content blocks to the model request

#### Scenario: OpenRouter MiMo model is active
- **WHEN** the active provider is `openrouter`
- **AND** the active model is `xiaomi/mimo-v2.5`
- **THEN** Deepy SHALL allow image attachments on user prompts

#### Scenario: OpenRouter MiMo Pro model is active
- **WHEN** the active provider is `openrouter`
- **AND** the active model is `xiaomi/mimo-v2.5-pro`
- **THEN** Deepy SHALL treat image attachments as unsupported
- **AND** it SHALL NOT send image content blocks to the model request

#### Scenario: Localhost GPT-5.6 model is active
- **WHEN** the active provider is `localhost`
- **AND** the active model is `gpt-5.6-sol`, `gpt-5.6-terra`, or `gpt-5.6-luna`
- **THEN** Deepy SHALL allow image attachments on user prompts

#### Scenario: DeepSeek model is active
- **WHEN** the active provider is `deepseek`
- **THEN** Deepy SHALL treat image attachments as unsupported
- **AND** it SHALL NOT send image content blocks to the model request

#### Scenario: Future Kimi model is not yet active
- **WHEN** the implementation contains internal image-content abstractions
- **THEN** those abstractions SHALL NOT require Xiaomi-specific naming
- **AND** Deepy SHALL NOT expose Kimi K2.6 image input as supported until a later change explicitly adds the model
