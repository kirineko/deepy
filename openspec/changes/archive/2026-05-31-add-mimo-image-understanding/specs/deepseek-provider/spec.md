## ADDED Requirements

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
