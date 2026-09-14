## MODIFIED Requirements

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
- **THEN** Deepy SHALL block an incompatible model request with guidance to select an image-capable model or start a text-only session
- **AND** it SHALL preserve the original image attachments and text context
- **AND** it SHALL NOT silently strip image history or mutate the original session

#### Scenario: Compacted image context
- **WHEN** retained model context contains only a text summary after compaction
- **THEN** Deepy SHALL permit that text context for a text-only model
- **AND** it SHALL preserve original attachments in persisted session history

## ADDED Requirements

### Requirement: Independent Web Search Usage
Deepy SHALL attribute built-in search usage separately from conversation-provider usage and context occupancy.

#### Scenario: Search usage known
- **WHEN** a DeepSeek search call returns token usage or search request counts
- **THEN** Deepy SHALL record actual input/output/cache usage and server search request counts with purpose web_search, provider deepseek and model deepseek-flash
- **AND** session totals SHALL include this consumption exactly once
- **AND** it SHALL NOT update the active conversation Context Window checkpoint from search-side tokens

#### Scenario: Unknown usage
- **WHEN** a search call fails without usage or returns incomplete usage metadata
- **THEN** Deepy SHALL keep unavailable values unknown rather than inventing zero usage

#### Scenario: Usage display
- **WHEN** a session contains MiMo, Kimi or CLI conversation and DeepSeek search calls
- **THEN** Deepy SHALL label search usage separately with its actual provider/model
- **AND** it SHALL preserve input suggestion, compaction and subagent usage distinctions
