## MODIFIED Requirements

### Requirement: Config Initialization

Deepy SHALL provide non-interactive and interactive configuration commands.

#### Scenario: User initializes config

- **WHEN** a user runs `deepy config init`
- **THEN** Deepy SHALL support `--api-key`, `--provider`, `--model`,
  `--base-url`, `--theme`, and `--force`
- **AND** written config files SHALL use permission mode `0600`
- **AND** the written TOML SHALL include `ui.theme`
- **AND** the written TOML SHALL include `config_version = 2`, `active_provider`, and the selected provider profile

#### Scenario: User runs setup

- **WHEN** a user runs `deepy config setup`
- **THEN** Deepy SHALL offer provider choices `DeepSeek`, `MiMo`, `Kimi`, and `CLI Proxy`
- **AND** `DeepSeek` SHALL be the default provider
- **AND** it SHALL collect the API key through password-style input
- **AND** it SHALL offer only models supported by the selected provider
- **AND** it SHALL use the selected provider's default base URL unless the user overrides it
- **AND** it SHALL offer provider-appropriate thinking choices
- **AND** it SHALL show numbered `auto`, `dark`, and `light` UI theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL write TOML with permission mode `0600`
- **AND** the written TOML SHALL include `ui.theme`

#### Scenario: Existing profile is edited

- **WHEN** setup edits a v2 provider profile
- **THEN** it SHALL preserve every other profile and unrelated configuration
- **AND** blank password input SHALL preserve that profile's saved key
- **AND** it SHALL indicate when a runtime environment key takes precedence

#### Scenario: Setup or reset is interrupted

- **WHEN** a user exits or the prompt stream ends during `deepy config setup` or
  `deepy config reset`
- **THEN** Deepy SHALL exit the configuration flow without printing a traceback
- **AND** if a config file existed before the flow, Deepy SHALL preserve or
  restore that file unchanged
- **AND** if no config file existed before the flow, Deepy SHALL leave no
  partial config file behind

### Requirement: Missing API Key Guidance

Deepy SHALL guide the user to configure a key before an interactive model turn.

#### Scenario: Interactive mode starts without a key

- **WHEN** Deepy starts interactive mode and the active provider has no resolved API key
- **THEN** Deepy SHALL enter setup guidance
- **AND** it SHALL NOT automatically open a browser

#### Scenario: Doctor runs without a key

- **WHEN** `deepy doctor --json` runs without a resolved key for the active provider
- **THEN** it SHALL return a non-zero status
- **AND** it SHALL suggest `deepy config setup`
- **AND** it SHALL NOT print a plaintext API key

#### Scenario: Only built-in search credentials are missing
- **WHEN** a non-DeepSeek active provider has a valid key and DeepSeek has no resolved key
- **THEN** Deepy SHALL allow conversation and report only built-in WebSearch as unavailable
- **AND** it SHALL preserve MCP search and WebFetch availability

### Requirement: Targeted Model Config Updates
Deepy SHALL merge profile changes without discarding inactive provider settings or unrelated configuration.

#### Scenario: User saves model settings
- **WHEN** a user edits provider/model/reasoning/base URL/key through any configuration surface
- **THEN** Deepy SHALL update only the selected profile and explicitly requested global fields
- **AND** it SHALL preserve other profiles and context, logging, notify, tools, MCP, input suggestions, audit, and UI settings
- **AND** it SHALL write atomically with permission mode `0600`

#### Scenario: Switch back
- **WHEN** DeepSeek is configured, then MiMo is configured, then DeepSeek is selected again
- **THEN** Deepy SHALL restore the saved DeepSeek model, reasoning, URL and key without asking to re-enter that key
- **AND** it SHALL change the active pointer without copying credentials between profiles

#### Scenario: Provider changes without explicit model
- **WHEN** a provider without saved settings is selected
- **THEN** Deepy SHALL use its defaults and resolve only that provider credentials

#### Scenario: Config path is unknown
- **WHEN** a flow is cancelled, the config path is unknown, or a write fails
- **THEN** Deepy SHALL preserve the previous persisted and in-memory settings and provide a concise diagnostic

## ADDED Requirements

### Requirement: Provider-Scoped Credential Resolution
Deepy SHALL separate saved credentials from environment-resolved credentials for every provider.

#### Scenario: Environment resolution
- **WHEN** credentials are resolved
- **THEN** Deepy SHALL prefer a non-empty explicitly configured profile environment reference, otherwise the provider default environment value, then the saved profile key
- **AND** defaults SHALL be `DEEPSEEK_API_KEY`, `MIMO_API_KEY`, `KIMI_API_KEY`, and `CLI_PROXY_API_KEY`
- **AND** the default Kimi reference SHALL fall back to `MOONSHOT_API_KEY` when KIMI_API_KEY is empty or absent

#### Scenario: No cross-provider override
- **WHEN** a generic `DEEPY_API_KEY` or another provider key exists
- **THEN** Deepy SHALL NOT use it as a cross-provider credential fallback

#### Scenario: Save under environment override
- **WHEN** a profile has a saved key and an environment key is active while another setting is saved
- **THEN** Deepy SHALL preserve the saved key and environment reference
- **AND** it SHALL NOT serialize the resolved environment secret

#### Scenario: Secret display
- **WHEN** config show/json, diagnostics, errors or session metadata are produced
- **THEN** Deepy SHALL redact secrets from every profile, including inactive profiles
- **AND** session metadata SHALL NOT contain resolved credentials

### Requirement: Supported Provider Model Catalog
Deepy SHALL validate model IDs against the selected provider catalog and persist the selection in that provider profile.

#### Scenario: Default model
- **WHEN** a new configuration omits provider and model
- **THEN** Deepy SHALL select `deepseek` and `deepseek-flash`

#### Scenario: Supported catalog
- **WHEN** the user selects a model
- **THEN** Deepy SHALL accept `deepseek-flash` for `deepseek`; `mimo-v2.5` and `mimo-v2.5-pro` for `mimo`; `kimi-k3` for `kimi`; and `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5` for `cli_proxy`

#### Scenario: Unsupported model
- **WHEN** a model is outside its provider catalog
- **THEN** Deepy SHALL reject the selection without changing saved or runtime settings
- **AND** it SHALL NOT infer support from a proxy model listing alone

### Requirement: Versioned Provider Profile Selection
Deepy SHALL use explicit provider profiles in version 2 TOML configuration.

#### Scenario: Profile selection
- **WHEN** Deepy loads `config_version = 2`
- **THEN** it SHALL resolve `active_provider` from `deepseek`, `mimo`, `kimi`, or `cli_proxy` and read `[providers.<id>]`
- **AND** it SHALL use `deepseek` when a new v2 configuration omits active_provider

#### Scenario: Default endpoints
- **WHEN** a profile omits base_url
- **THEN** Deepy SHALL use `https://api.deepseek.com`, `https://api.xiaomimimo.com/v1`, `https://api.moonshot.cn/v1`, or `http://127.0.0.1:8317/v1` for the respective provider

#### Scenario: Removed configuration
- **WHEN** an old shared `[model]` format, removed provider ID, or unsupported config version is loaded
- **THEN** Deepy SHALL report that explicit reconfiguration is required
- **AND** it SHALL NOT infer a provider from the URL, silently migrate the file, or overwrite it before completed user-directed setup/reset

### Requirement: Provider Profile Reasoning
Deepy SHALL persist `reasoning` independently in each provider profile and expose only supported choices.

#### Scenario: Provider reasoning
- **WHEN** a user selects a reasoning mode
- **THEN** Deepy SHALL offer `none/high/max` for DeepSeek, `disabled/enabled` for MiMo, `low/high/max` for Kimi, and model-supported efforts for CLI Proxy

#### Scenario: Defaults
- **WHEN** a new profile omits reasoning
- **THEN** Deepy SHALL default to `max` for DeepSeek and Kimi, `enabled` for MiMo, and `medium` for the default CLI Proxy model

#### Scenario: Invalid reasoning
- **WHEN** a selected effort is unsupported by the provider/model
- **THEN** Deepy SHALL reject it without saving an invalid profile
- **AND** it SHALL NOT silently translate Kimi reasoning to unsupported disabled thinking

### Requirement: Responses Model Capability Metadata
Deepy SHALL expose image capability by provider, model and API through one consistent catalog.

#### Scenario: Image models
- **WHEN** the Responses catalog is loaded
- **THEN** Deepy SHALL mark `deepseek/deepseek-flash`, `mimo/mimo-v2.5`, `kimi/kimi-k3`, and all five supported CLI Proxy models as image capable

#### Scenario: Text-only model
- **WHEN** `mimo/mimo-v2.5-pro` is selected
- **THEN** Deepy SHALL mark image input unsupported

#### Scenario: Consistent consumers
- **WHEN** UI, validation, prompt or tool-image serialization checks capability
- **THEN** each SHALL use the same catalog decision
- **AND** audio, video, PDF input and media generation SHALL NOT be advertised as supported by this change

## REMOVED Requirements

### Requirement: DeepSeek Model Configuration
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "Supported Provider Model Catalog" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.

### Requirement: Provider Selection Configuration
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "Versioned Provider Profile Selection" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.

### Requirement: Reasoning Mode Configuration
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "Provider Profile Reasoning" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.

### Requirement: Image Input Model Capability Metadata
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "Responses Model Capability Metadata" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.
