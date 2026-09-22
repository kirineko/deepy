## MODIFIED Requirements

### Requirement: Direct Model Command Forms
Deepy SHALL support direct commands consistent with profile-aware model selection.

#### Scenario: User lists supported models
- **WHEN** a user runs /model list
- **THEN** Deepy SHALL group supported models by provider and show supported reasoning and image capabilities

#### Scenario: User sets DeepSeek model directly
- **WHEN** a user runs `/model set deepseek-flash` or `/model set mimo mimo-v2.6-flash enabled` or an equivalent supported provider/model command
- **THEN** Deepy SHALL save the target profile selection and preserve its reasoning unless explicitly changed

#### Scenario: User sets provider directly
- **WHEN** a user runs /model provider with deepseek, mimo, kimi or cli_proxy
- **THEN** Deepy SHALL restore that provider profile and credentials, using defaults only for unset settings

#### Scenario: User sets reasoning mode directly
- **WHEN** a user runs /model reasoning or /model thinking with a supported choice
- **THEN** Deepy SHALL update only the active profile reasoning and retain provider/model

#### Scenario: User provides invalid model command arguments
- **WHEN** arguments reference a removed provider/model or unsupported reasoning mode
- **THEN** Deepy SHALL show concise usage guidance and preserve saved and runtime settings

#### Scenario: User sets provider and MiMo model directly
- **WHEN** a user runs /model set mimo mimo-v2.6-flash enabled or /model set mimo mimo-v2.6-pro disabled
- **THEN** Deepy SHALL update the MiMo profile and active selection without changing other profiles

#### Scenario: User sets switch-only thinking directly
- **WHEN** a user runs /model thinking enabled or /model thinking disabled for MiMo
- **THEN** Deepy SHALL update the active profile reasoning while retaining its model

#### Scenario: MiMo catalog is presented in either UI
- **WHEN** classic or modern UI presents MiMo model choices, completions or current model help
- **THEN** it SHALL offer only `mimo-v2.6-flash` and `mimo-v2.6-pro` as MiMo models and show image support for both where capabilities are displayed
- **AND** current command examples SHALL use the new model IDs
- **AND** removed IDs SHALL appear only where needed for rejection or migration guidance, or as historical session identity
