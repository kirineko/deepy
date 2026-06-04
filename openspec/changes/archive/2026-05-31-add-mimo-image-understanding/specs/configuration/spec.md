## ADDED Requirements

### Requirement: Image Input Model Capability Metadata
Deepy SHALL expose image-input support as explicit model capability metadata.

#### Scenario: Xiaomi MiMo image-capable models are loaded
- **WHEN** Deepy builds the Xiaomi model catalog
- **THEN** `mimo-v2.5` SHALL be marked as supporting image input
- **AND** `mimo-v2.5-pro` SHALL be marked as not supporting image input

#### Scenario: OpenRouter MiMo image-capable models are loaded
- **WHEN** Deepy builds the OpenRouter model catalog
- **THEN** `xiaomi/mimo-v2.5` SHALL be marked as supporting image input
- **AND** `xiaomi/mimo-v2.5-pro` SHALL be marked as not supporting image input

#### Scenario: DeepSeek models are loaded
- **WHEN** Deepy builds the DeepSeek model catalog
- **THEN** DeepSeek models SHALL be marked as not supporting image input

#### Scenario: Custom OpenRouter model is configured
- **WHEN** Deepy loads a custom OpenRouter model id that is not one of the curated MiMo image-capable model ids
- **THEN** Deepy SHALL treat image input as unsupported for that model
- **AND** it SHALL preserve the custom model id behavior for text-only use

#### Scenario: Future Kimi capability is added
- **WHEN** a future change adds Kimi K2.6 as a supported model
- **THEN** Deepy SHALL be able to mark image support through the same capability metadata
- **AND** it SHALL NOT require a new prompt attachment model
