## ADDED Requirements

### Requirement: Read Tool Image Follow-Up Compatibility
Deepy's existing image follow-up messages from `Read` SHALL remain compatible with the shared image input contract.

#### Scenario: Read loads an image file
- **WHEN** the model invokes `Read` for a supported image file
- **THEN** Deepy SHALL return a structured follow-up message containing image content
- **AND** the image content SHALL use the same internal image attachment representation accepted by model input normalization

#### Scenario: Read image follow-up is converted for Chat Completions
- **WHEN** a `Read` image follow-up message is included in model input for a supported image model
- **THEN** Deepy SHALL convert it to the same Chat Completions image-url shape used for pasted prompt images
- **AND** it SHALL preserve the base64 data URL and MIME type

#### Scenario: Read image follow-up targets unsupported model
- **WHEN** a `Read` image follow-up message would be sent to a model that does not support image input
- **THEN** Deepy SHALL avoid sending image content blocks to that model
- **AND** it SHALL surface a concise model incompatibility error rather than sending an unsupported payload
