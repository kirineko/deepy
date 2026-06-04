## ADDED Requirements

### Requirement: Image Attachment Session Persistence
Deepy SHALL persist user turns with image attachments so supported image conversations remain resumable.

#### Scenario: Image prompt is recorded
- **WHEN** a user submits a prompt with one or more image attachments
- **THEN** Deepy SHALL record the user turn with structured text and image content
- **AND** the persisted item SHALL contain enough information to replay the image context in a resumed session

#### Scenario: Image session is resumed
- **WHEN** the user resumes a session containing image prompt turns
- **THEN** Deepy SHALL load the image content as structured session input
- **AND** subsequent model turns SHALL preserve the conversation context when the active model supports image input

#### Scenario: Image session is resumed with unsupported model
- **WHEN** the user resumes a session containing image prompt turns
- **AND** the active model does not support image input
- **THEN** Deepy SHALL ignore image content blocks for that model turn
- **AND** it SHALL preserve and send the remaining text context
- **AND** it SHALL NOT block the model request with an incompatibility message

### Requirement: Image Attachment Preview Redaction
Deepy SHALL keep image session previews readable by redacting raw image data in normal user-facing displays.

#### Scenario: Session list previews image prompt
- **WHEN** Deepy renders a session list entry whose title or preview comes from an image prompt
- **THEN** it SHALL show prompt text and compact image labels
- **AND** it SHALL NOT show raw base64 data or full data URLs

#### Scenario: Session show renders image prompt
- **WHEN** Deepy renders session history containing image content blocks
- **THEN** it SHALL show compact image labels or image metadata
- **AND** it SHALL NOT show raw base64 data in normal non-debug output

#### Scenario: Context tokens are estimated for image prompts
- **WHEN** Deepy estimates local context pressure for persisted image prompt items
- **THEN** it SHALL account for image content conservatively
- **AND** it SHALL avoid expanding redacted display labels back into raw base64 for user-facing context summaries
