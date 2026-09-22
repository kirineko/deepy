# image-understanding-input Specification

## Purpose

Deepy validates and preserves image attachments across prompts, tool results and local sessions, and sends them through Responses only for image-capable catalog models.

## Requirements

### Requirement: Prompt Image Attachments
Deepy SHALL support structured image attachments on user prompts for catalogued image-capable Responses models.

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

### Requirement: Image Attachment Validation
Deepy SHALL validate images at paste time and revalidate the complete request against current model capabilities before sending.

#### Scenario: Supported image is pasted
- **WHEN** an image has a supported MIME type and meets active limits
- **THEN** Deepy SHALL attach it with a stable label and preserve existing draft text

#### Scenario: Limits
- **WHEN** Deepy validates image input
- **THEN** it SHALL accept only PNG, JPEG, WebP or GIF, with application limits of 10 MiB per image, eight images per submitted turn, and 32 MiB for the encoded request body
- **AND** it SHALL also enforce any smaller provider-specific limit
- **AND** request-body validation SHALL include replayed history images

#### Scenario: Unsupported image format is pasted
- **WHEN** MIME type, image size or image count exceeds a limit
- **THEN** Deepy SHALL reject the new attachment with a concise non-blocking explanation and preserve the draft

#### Scenario: Model changes after paste
- **WHEN** a draft contains images and the selected model no longer supports them
- **THEN** Deepy SHALL preserve the draft and block incompatible submission with guidance to remove attachments or select an image-capable model
- **AND** it SHALL NOT silently drop images or send an unsupported payload

#### Scenario: Oversized image is pasted
- **WHEN** clipboard image data exceeds the active size limit
- **THEN** Deepy SHALL reject the image with a non-blocking error and preserve the current prompt text

### Requirement: Image Content Transport
Deepy SHALL serialize image prompts as valid Responses input content while preserving user-visible attachment semantics.

#### Scenario: Image prompt is converted for model input
- **WHEN** a supported image prompt is sent
- **THEN** Deepy SHALL send text as input_text followed by ordered input_image parts containing base64 data URLs
- **AND** it SHALL NOT append base64 or display labels to natural-language prompt text

#### Scenario: Image-only prompt is converted for model input
- **WHEN** a user submits images without prompt text
- **THEN** Deepy SHALL prepend concise image-description guidance without requesting tool execution or file modification
- **AND** the transcript SHALL continue displaying compact attachment labels

#### Scenario: Provider rejects image request
- **WHEN** an image request returns a provider error
- **THEN** Deepy SHALL surface a recoverable model-turn error and keep the interactive session usable

### Requirement: Responses Image Model Set
Deepy SHALL support images only for model/API combinations explicitly marked image-capable in the shared catalog.

#### Scenario: Supported image selection
- **WHEN** the active model is DeepSeek `deepseek-flash`, MiMo `mimo-v2.6-flash` or `mimo-v2.6-pro`, Kimi `kimi-k3`, or one of the five supported CLI Proxy models
- **THEN** Deepy SHALL allow validated image attachments through Responses

#### Scenario: MiMo Pro
- **WHEN** the active model is `mimo-v2.6-pro`
- **THEN** Deepy SHALL accept validated image pastes and send image content through Responses

#### Scenario: Other modalities
- **WHEN** an input path checks audio, video, PDF or generation capabilities
- **THEN** Deepy SHALL NOT advertise these as native supported modalities in this change

#### Scenario: MiMo image paths remain consistent
- **WHEN** either supported MiMo V2.6 model receives validated images from a prompt, Read result, replayed history or a subagent using that model
- **THEN** Deepy SHALL preserve the images through the shared Responses image transport
- **AND** existing MIME, per-image, per-turn and encoded-request limits SHALL still apply

### Requirement: Recoverable Read Image Batch Validation
Deepy SHALL validate the aggregate image count of a batch Read result before returning image attachments to the agent.

#### Scenario: Read batch exceeds the image limit
- **WHEN** a batch Read produces more than eight images
- **THEN** Read SHALL return an error explaining the limit and asking for a smaller batch
- **AND** the error SHALL contain no image attachments
- **AND** the agent SHALL be able to receive the tool error and continue with a smaller Read request

#### Scenario: Read batch is within the image limit
- **WHEN** a batch Read produces at most eight images with optional text targets
- **THEN** Deepy SHALL preserve the successful image attachments and text results in target order
- **AND** text targets SHALL NOT count toward the image limit
