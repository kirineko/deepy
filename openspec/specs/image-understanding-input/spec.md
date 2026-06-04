# image-understanding-input Specification

## Purpose
TBD - created by archiving change add-mimo-image-understanding. Update Purpose after archive.
## Requirements
### Requirement: Prompt Image Attachments
Deepy SHALL support structured image attachments on user prompts for explicitly supported MiMo image-understanding models.

#### Scenario: Supported model receives pasted images
- **WHEN** the active model supports image input
- **AND** the user submits prompt text with one or more pasted image attachments
- **THEN** Deepy SHALL send a multipart user message containing the text prompt and each image attachment
- **AND** the text part SHALL precede the image parts
- **AND** Deepy SHALL preserve the attachment order selected by the user

#### Scenario: Prompt has only image attachments
- **WHEN** the active model supports image input
- **AND** the user submits one or more image attachments without prompt text
- **THEN** Deepy SHALL still send a valid multipart user message
- **AND** it SHALL include a concise default text part asking the model to describe the image rather than infer tool actions
- **AND** it SHALL include image parts for every attachment

#### Scenario: Unsupported model receives pasted image
- **WHEN** the active model does not support image input
- **AND** the clipboard paste contains image data
- **THEN** Deepy SHALL show a concise non-blocking assistant-visible message
- **AND** it SHALL discard the pasted image attachment
- **AND** it SHALL preserve the current prompt text
- **AND** it SHALL keep accepting text input and text-only submission

### Requirement: Supported Image Model Set
Deepy SHALL treat image input as supported only for the initial MiMo model allowlist.

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

#### Scenario: DeepSeek model is active
- **WHEN** the active provider is `deepseek`
- **THEN** Deepy SHALL treat image attachments as unsupported
- **AND** it SHALL NOT send image content blocks to the model request

#### Scenario: Future Kimi model is not yet active
- **WHEN** the implementation contains internal image-content abstractions
- **THEN** those abstractions SHALL NOT require Xiaomi-specific naming
- **AND** Deepy SHALL NOT expose Kimi K2.6 image input as supported until a later change explicitly adds the model

### Requirement: Image Attachment Validation
Deepy SHALL validate pasted image attachments before adding them to prompt state.

#### Scenario: Supported image is pasted
- **WHEN** clipboard image data has a supported MIME type and does not exceed the configured image size limit
- **THEN** Deepy SHALL attach the image to the prompt
- **AND** it SHALL assign the image a stable display label for that prompt

#### Scenario: Unsupported image format is pasted
- **WHEN** clipboard image data has an unsupported MIME type
- **THEN** Deepy SHALL reject the image with a concise non-blocking error
- **AND** it SHALL preserve the current prompt text

#### Scenario: Oversized image is pasted
- **WHEN** clipboard image data exceeds the configured image size limit
- **THEN** Deepy SHALL reject the image with a concise non-blocking error
- **AND** it SHALL preserve the current prompt text

### Requirement: Image Content Transport
Deepy SHALL use OpenAI-compatible multipart content blocks for supported image prompts.

#### Scenario: Image prompt is converted for model input
- **WHEN** Deepy prepares a supported image prompt for the model
- **THEN** it SHALL represent prompt text as a text content block
- **AND** it SHALL represent each image as an image URL content block containing a `data:<mime>;base64,<data>` URL
- **AND** it SHALL NOT append image labels or base64 data to the natural-language prompt text

#### Scenario: Image-only prompt is converted for model input
- **WHEN** Deepy prepares a supported prompt that contains image attachments and no user prompt text
- **THEN** it SHALL prepend a concise default text content block before the image URL blocks
- **AND** the default text SHALL ask for image description without tool execution or file modification
- **AND** the displayed transcript MAY continue to show only the compact image labels

#### Scenario: Provider rejects image request
- **WHEN** a supported image model returns a provider API error for an image request
- **THEN** Deepy SHALL surface the provider error through the existing model-turn error path
- **AND** the interactive session SHALL continue
