## MODIFIED Requirements

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
