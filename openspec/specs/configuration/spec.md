# Configuration Specification

## Purpose

Deepy uses versioned TOML provider profiles to retain independent credentials, models, endpoints and reasoning settings, with ephemeral environment overrides and atomic private writes.

## Requirements

### Requirement: TOML-Only Config

Deepy SHALL use TOML as the only supported persistent configuration format.

#### Scenario: Default config path is used

- **WHEN** Deepy needs to read or write persistent configuration
- **THEN** it SHALL use `~/.deepy/config.toml` by default

#### Scenario: JSON config is present

- **WHEN** a user provides or references a `.json` config file
- **THEN** Deepy SHALL reject it instead of silently reading legacy JSON

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

### Requirement: UI Theme Configuration

Deepy SHALL persist the user's terminal UI theme selection in TOML
configuration.

#### Scenario: Config without UI theme is loaded

- **WHEN** Deepy loads a TOML config that has no `[ui]` section or no `ui.theme`
  value
- **THEN** Deepy SHALL resolve the saved UI theme as `auto`

#### Scenario: Config has an invalid UI theme

- **WHEN** Deepy loads a TOML config whose `ui.theme` is not `auto`, `dark`, or
  `light`
- **THEN** Deepy SHALL resolve the saved UI theme as `auto`

#### Scenario: User shows configured theme

- **WHEN** a user runs `deepy config theme`
- **THEN** Deepy SHALL print the saved UI theme and the currently resolved
  runtime theme

#### Scenario: User updates configured theme

- **WHEN** a user runs `deepy config theme auto`, `deepy config theme dark`, or
  `deepy config theme light`
- **THEN** Deepy SHALL write the selected value to `ui.theme`
- **AND** it SHALL preserve existing model, context, logging, notify, and tool
  settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: User provides invalid configured theme

- **WHEN** a user runs `deepy config theme` with a value other than `auto`,
  `dark`, or `light`
- **THEN** Deepy SHALL return a non-zero status
- **AND** it SHALL NOT change the saved config

#### Scenario: User resets configuration

- **WHEN** a user runs `deepy config reset`
- **THEN** Deepy SHALL delete the existing TOML config file when it exists
- **AND** it SHALL guide the user through interactive setup again
- **AND** it SHALL write the replacement TOML config with permission mode `0600`

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

### Requirement: Context Compaction Configuration

Deepy SHALL provide TOML configuration for the canonical context compaction
policy.

#### Scenario: Default compaction config is loaded

- **WHEN** Deepy loads config without explicit compaction preservation or reserved
  context values
- **THEN** it SHALL use default values for reserved context tokens and recent
  context preservation
- **AND** `window_tokens` and `compact_trigger_ratio` SHALL feed the canonical
  auto compact policy

#### Scenario: Reserved context tokens are configured

- **WHEN** Deepy loads `[context].reserved_context_tokens`
- **THEN** it SHALL use that value when deciding whether automatic compaction is
  required
- **AND** invalid non-positive values SHALL fall back to the default

#### Scenario: Recent message preservation is configured

- **WHEN** Deepy loads `[context].compact_preserve_recent_messages`
- **THEN** it SHALL use that value when selecting recent messages to keep after
  compaction
- **AND** invalid non-positive values SHALL fall back to the default

#### Scenario: Recent token preservation is configured

- **WHEN** Deepy loads `[context].compact_preserve_recent_tokens`
- **THEN** it SHALL use that value as an optional token budget for preserved
  recent context
- **AND** invalid non-positive values SHALL be ignored

#### Scenario: Config is shown

- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include resolved compaction policy values
- **AND** it SHALL not present removed compact threshold aliases as authoritative
  policy values

#### Scenario: Removed compact threshold config is present

- **WHEN** Deepy loads a legacy `compact_prompt_token_threshold` field from an
  old config file
- **THEN** Deepy SHALL ignore the field entirely
- **AND** it SHALL NOT expose the removed field as part of the resolved runtime
  config

### Requirement: MCP Configuration Files
Deepy SHALL separate Deepy MCP policy from MCP server definitions.

#### Scenario: Deepy MCP policy is loaded
- **WHEN** Deepy loads persistent configuration
- **THEN** it SHALL read Deepy MCP policy from `~/.deepy/config.toml`
- **AND** the policy SHALL include whether MCP is enabled, connection timeouts,
  cleanup timeouts, MCP session read timeout, tool-list caching preference,
  project-config permission, and MCP web-search preference settings

#### Scenario: Global MCP server definitions are loaded
- **WHEN** MCP is enabled and `~/.deepy/mcp.json` exists
- **THEN** Deepy SHALL read MCP server definitions from the file's `mcpServers`
  object
- **AND** it SHALL support server entries that define stdio or Streamable HTTP
  transports

#### Scenario: MCP server definition file is missing
- **WHEN** MCP is enabled and `~/.deepy/mcp.json` does not exist
- **THEN** Deepy SHALL treat the configured MCP server list as empty
- **AND** it SHALL continue without an error

#### Scenario: Deepy config is shown
- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include resolved MCP policy values
- **AND** it SHALL NOT include plaintext secret values from MCP server
  environment variables or headers

### Requirement: MCP Server Definition Validation
Deepy SHALL validate MCP server definitions before creating SDK MCP server
instances.

#### Scenario: Stdio server definition is valid
- **WHEN** an enabled MCP server definition has `transport = "stdio"` or omits
  transport while providing a command
- **THEN** Deepy SHALL require a non-empty command
- **AND** it SHALL accept optional args, env, roles, and tool preference metadata

#### Scenario: Streamable HTTP server definition is valid
- **WHEN** an enabled MCP server definition has `transport = "streamable_http"`
- **THEN** Deepy SHALL require a non-empty URL
- **AND** it SHALL accept optional headers, roles, and tool preference metadata

#### Scenario: MCP server definition is invalid
- **WHEN** an enabled MCP server definition is missing required fields for its
  transport or uses an unsupported transport
- **THEN** Deepy SHALL skip that server
- **AND** it SHALL record a concise validation error for status display

#### Scenario: Environment variable placeholder is configured
- **WHEN** an MCP server env or header value uses a placeholder such as
  `${TAVILY_API_KEY}`
- **THEN** Deepy SHALL resolve it from the process environment before creating
  the MCP server
- **AND** unresolved placeholders SHALL cause that server to be skipped with a
  concise validation error

### Requirement: Input Suggestion Configuration
Deepy SHALL persist input suggestion enablement in TOML configuration with a
default of enabled.

#### Scenario: Config omits input suggestion setting
- **WHEN** Deepy loads a TOML config with no input suggestion enabled setting
- **THEN** Deepy SHALL resolve input suggestions as enabled

#### Scenario: Config disables input suggestions
- **WHEN** Deepy loads a TOML config whose input suggestion enabled setting is
  false
- **THEN** Deepy SHALL disable input suggestion generation and display for
  interactive sessions

#### Scenario: User toggles input suggestions
- **WHEN** a user runs `/input-suggestion` in an interactive terminal UI
- **THEN** Deepy SHALL persist the toggled enabled state to TOML
- **AND** it SHALL preserve existing model, context, logging, notify, tools, MCP,
  and UI theme settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: Config is shown
- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include the resolved input suggestion enabled state
- **AND** it SHALL NOT expose any user-customizable suggestion model field

### Requirement: Subagent Configuration Locations

Deepy SHALL store and discover custom subagent definitions under Deepy-owned
configuration directories.

#### Scenario: Project subagent directory exists

- **WHEN** the current project contains `.deepy/subagents`
- **THEN** Deepy SHALL discover valid Markdown subagent definitions in that
  directory
- **AND** it SHALL treat them as project-scoped subagents

#### Scenario: User subagent directory exists

- **WHEN** the user home contains `~/.deepy/subagents`
- **THEN** Deepy SHALL discover valid Markdown subagent definitions in that
  directory
- **AND** it SHALL treat them as user-scoped subagents

#### Scenario: Agent Skills directory exists

- **WHEN** the current project or user home contains `.agents/skills`
- **THEN** Deepy SHALL continue treating that directory as Agent Skills storage
- **AND** it SHALL NOT load files from `.agents/skills` as subagent definitions

### Requirement: Subagent Policy Configuration

Deepy SHALL allow project policy extensions for constrained subagent command
execution.

#### Scenario: Project test-shell policy extends allowlist

- **WHEN** project configuration declares additional `test_shell` allowed command
  patterns
- **THEN** Deepy SHALL consider those patterns during `test_shell` policy
  classification
- **AND** it SHALL still apply global deny rules for destructive and publishing
  commands

#### Scenario: Project test-shell policy requires approval

- **WHEN** project configuration declares additional `test_shell`
  approval-required command patterns
- **THEN** Deepy SHALL classify matching commands as approval-required
- **AND** it SHALL require user approval before execution

#### Scenario: Subagent policy is invalid

- **WHEN** project subagent policy contains invalid command patterns or invalid
  values
- **THEN** Deepy SHALL ignore the invalid policy entries with diagnostics
- **AND** it SHALL continue using built-in safe defaults

### Requirement: UI View Mode Configuration
Deepy SHALL persist the user's reasoning display view mode in TOML configuration with a unified default of concise.

#### Scenario: Config omits view mode
- **WHEN** Deepy loads a TOML config with no UI view mode setting
- **THEN** Deepy SHALL resolve the UI view mode as `concise`
- **AND** live reasoning transcript text SHALL be hidden by default

#### Scenario: Config sets concise view mode
- **WHEN** Deepy loads `[ui].view_mode = "concise"`
- **THEN** Deepy SHALL hide live reasoning transcript text in interactive UI surfaces
- **AND** it SHALL NOT disable provider reasoning behavior

#### Scenario: Config sets full view mode
- **WHEN** Deepy loads `[ui].view_mode = "full"`
- **THEN** Deepy SHALL show live reasoning transcript text in interactive UI surfaces that support reasoning display
- **AND** it SHALL NOT change provider reasoning strength

#### Scenario: Config has invalid view mode
- **WHEN** Deepy loads a TOML config whose UI view mode is not `concise` or `full`
- **THEN** Deepy SHALL resolve the UI view mode as `concise`
- **AND** it SHALL continue loading the rest of the configuration

#### Scenario: User toggles view mode
- **WHEN** a user changes the view mode through an interactive `/view` command
- **THEN** Deepy SHALL persist the selected view mode to TOML
- **AND** it SHALL preserve existing model, context, logging, notify, tools, MCP, input suggestion, and UI theme settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: Config is shown
- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include the resolved UI view mode

### Requirement: Audit Mode Configuration

Deepy SHALL support TOML configuration for the default system audit mode.

#### Scenario: Config omits audit mode

- **WHEN** Deepy loads TOML configuration without an audit mode value
- **THEN** Deepy SHALL use `yolo` as the default audit mode for backward
  compatibility

#### Scenario: Config sets valid audit mode

- **WHEN** Deepy loads TOML configuration with audit mode `normal`, `auto`, or
  `yolo`
- **THEN** Deepy SHALL use that value as the default audit mode for new
  sessions

#### Scenario: Config sets invalid audit mode

- **WHEN** Deepy loads TOML configuration with an invalid audit mode value
- **THEN** Deepy SHALL fall back to the default audit mode
- **AND** Deepy SHALL make the invalid value discoverable through configuration
  validation or status diagnostics

#### Scenario: Runtime audit mode changes

- **WHEN** the user changes audit mode from an interactive runtime control such
  as `Shift+Tab`
- **THEN** Deepy SHALL update the active process audit mode immediately
- **AND** Deepy SHALL NOT persist the new mode to TOML configuration unless the
  user explicitly invokes a persistent configuration command

### Requirement: MCP Approval Override Configuration

Deepy SHALL support TOML configuration for MCP server/tool pairs that may be
auto-approved in `auto` audit mode.

#### Scenario: Config marks MCP tool as safe

- **WHEN** TOML configuration lists a specific MCP server/tool pair as safe for
  automatic approval
- **THEN** Deepy SHALL treat that pair as auto-approved only while the active
  audit mode is `auto` or `yolo`

#### Scenario: Config marks MCP wildcard unsafe

- **WHEN** TOML configuration does not list a specific MCP server/tool pair as
  safe
- **THEN** Deepy SHALL require approval for that MCP tool in `normal` and
  `auto` modes

#### Scenario: Config is written

- **WHEN** Deepy writes TOML configuration containing audit settings
- **THEN** the written config SHALL preserve existing model, context, logging,
  notify, tool, MCP, and UI settings
- **AND** the config file SHALL use permission mode `0600`

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
