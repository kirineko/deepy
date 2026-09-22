## MODIFIED Requirements

### Requirement: Supported Provider Model Catalog
Deepy SHALL validate model IDs against the selected provider catalog and persist the selection in that provider profile.

#### Scenario: Default model
- **WHEN** a new configuration omits provider and model
- **THEN** Deepy SHALL select `deepseek` and `deepseek-flash`

#### Scenario: Supported catalog
- **WHEN** the user selects a model
- **THEN** Deepy SHALL accept `deepseek-flash` for `deepseek`; `mimo-v2.6-flash` and `mimo-v2.6-pro` for `mimo`; `kimi-k3` for `kimi`; and `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5` for `cli_proxy`

#### Scenario: Unsupported model
- **WHEN** a model is outside its provider catalog
- **THEN** Deepy SHALL reject the selection without changing saved or runtime settings
- **AND** it SHALL NOT infer support from a proxy model listing alone

#### Scenario: Default MiMo model
- **WHEN** a MiMo provider profile omits its model
- **THEN** Deepy SHALL select `mimo-v2.6-flash`
- **AND** the MiMo catalog SHALL contain exactly `mimo-v2.6-flash` and `mimo-v2.6-pro`

#### Scenario: Removed MiMo selection
- **WHEN** a user attempts to select `mimo-v2.5` or `mimo-v2.5-pro`
- **THEN** Deepy SHALL reject the selection and identify `mimo-v2.6-flash` or `mimo-v2.6-pro`, respectively, as the replacement
- **AND** saved and runtime settings SHALL remain unchanged

### Requirement: Responses Model Capability Metadata
Deepy SHALL expose image capability by provider, model and API through one consistent catalog.

#### Scenario: Image models
- **WHEN** the Responses catalog is loaded
- **THEN** Deepy SHALL mark `deepseek/deepseek-flash`, `mimo/mimo-v2.6-flash`, `mimo/mimo-v2.6-pro`, `kimi/kimi-k3`, and all five supported CLI Proxy models as image capable

#### Scenario: MiMo Pro image capability
- **WHEN** `mimo/mimo-v2.6-pro` is selected
- **THEN** Deepy SHALL mark image input supported

#### Scenario: Text-only model
- **WHEN** a model is explicitly marked text-only by the shared capability catalog
- **THEN** Deepy SHALL mark image input unsupported
- **AND** neither supported MiMo V2.6 model SHALL be marked text-only

#### Scenario: Consistent consumers
- **WHEN** UI, validation, prompt or tool-image serialization checks capability
- **THEN** each SHALL use the same catalog decision
- **AND** audio, video, PDF input and media generation SHALL NOT be advertised as supported by this change

## ADDED Requirements

### Requirement: Retired MiMo Configuration Guidance
Deepy SHALL reject removed MiMo model references in saved provider configuration with actionable replacement guidance and without silently changing the file.

#### Scenario: Active or inactive profile selects a removed model
- **WHEN** settings load a MiMo profile selecting `mimo-v2.5` or `mimo-v2.5-pro`, whether active or inactive
- **THEN** Deepy SHALL report the removed model and identify `providers.mimo.model` as requiring an explicit edit
- **AND** it SHALL suggest `mimo-v2.6-flash` for `mimo-v2.5` and `mimo-v2.6-pro` for `mimo-v2.5-pro`
- **AND** it SHALL preserve the configuration file and SHALL NOT reveal credentials

#### Scenario: Model limits still reference a removed model
- **WHEN** a MiMo profile has a valid selected model but its model-limit overrides contain either removed model ID
- **THEN** Deepy SHALL reject that configuration and identify the offending `providers.mimo.model_limits` entry
- **AND** it SHALL instruct the user to rename the entry to the corresponding V2.6 replacement or remove that override
- **AND** it SHALL NOT silently rename, discard or write configuration values

#### Scenario: User explicitly updates old configuration
- **WHEN** the user replaces the retired model and any retired model-limit keys with the corresponding V2.6 IDs and all remaining settings are valid
- **THEN** Deepy SHALL load the updated configuration using the existing provider credentials, URL, reasoning and valid limit overrides
- **AND** it SHALL NOT rewrite stored session history or historical model identities
