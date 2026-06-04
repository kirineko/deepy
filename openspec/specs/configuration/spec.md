# Configuration Specification

## Purpose

Deepy uses TOML-only local configuration with safe defaults for DeepSeek and long
context sessions.
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
- **AND** the written TOML SHALL include `model.provider` when a provider is selected or inferred

#### Scenario: User runs setup

- **WHEN** a user runs `deepy config setup`
- **THEN** Deepy SHALL offer provider choices `DeepSeek`, `OpenRouter`, and `Xiaomi`
- **AND** `DeepSeek` SHALL be the default provider
- **AND** it SHALL collect the API key through password-style input
- **AND** it SHALL offer only models supported by the selected provider
- **AND** when provider is `OpenRouter`, it SHALL also allow the user to paste
  a custom model name copied from the OpenRouter model page
- **AND** it SHALL use the selected provider's default base URL unless the user overrides it
- **AND** it SHALL offer provider-appropriate thinking choices
- **AND** it SHALL show numbered `auto`, `dark`, and `light` UI theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL write TOML with permission mode `0600`
- **AND** the written TOML SHALL include `ui.theme`

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

- **WHEN** Deepy starts interactive mode and no API key is configured
- **THEN** Deepy SHALL enter setup guidance
- **AND** it SHALL NOT automatically open a browser

#### Scenario: Doctor runs without a key

- **WHEN** `deepy doctor --json` runs without a configured API key
- **THEN** it SHALL return a non-zero status
- **AND** it SHALL suggest `deepy config setup`
- **AND** it SHALL NOT print a plaintext API key

### Requirement: DeepSeek Model Configuration
Deepy SHALL persist and validate the active model for the resolved provider in
TOML configuration.

#### Scenario: Default model is loaded
- **WHEN** Deepy loads config with no model name and no explicit provider
- **THEN** Deepy SHALL use provider `deepseek`
- **AND** it SHALL use `deepseek-v4-pro` as the active model

#### Scenario: Supported DeepSeek model is loaded
- **WHEN** Deepy loads config with provider `deepseek`
- **AND** `model.name` is `deepseek-v4-pro` or `deepseek-v4-flash`
- **THEN** Deepy SHALL use the configured model as the active model

#### Scenario: Supported OpenRouter model is loaded
- **WHEN** Deepy loads config with provider `openrouter`
- **AND** `model.name` is `xiaomi/mimo-v2.5-pro` or `xiaomi/mimo-v2.5`
- **THEN** Deepy SHALL use the configured model as the active model

#### Scenario: Custom OpenRouter model is loaded
- **WHEN** Deepy loads config with provider `openrouter`
- **AND** `model.name` is a non-empty model id copied from OpenRouter
- **THEN** Deepy SHALL preserve the configured model as the active model
- **AND** Deepy SHALL treat correctness of that model id as the user's responsibility

#### Scenario: Supported Xiaomi model is loaded
- **WHEN** Deepy loads config with provider `xiaomi`
- **AND** `model.name` is `mimo-v2.5-pro` or `mimo-v2.5`
- **THEN** Deepy SHALL use the configured model as the active model

#### Scenario: Invalid model is selected through Deepy commands
- **WHEN** a user attempts to select a model that is not in the selected provider's model catalog
- **THEN** Deepy SHALL reject the value with a concise usage message
- **AND** it SHALL NOT change the saved config

### Requirement: Reasoning Mode Configuration
Deepy SHALL expose provider-appropriate thinking behavior while persisting
through existing TOML fields.

#### Scenario: DeepSeek reasoning mode none is loaded
- **WHEN** Deepy loads config for provider `deepseek` whose resolved reasoning mode is `none`
- **THEN** Deepy SHALL treat thinking as disabled

#### Scenario: DeepSeek reasoning mode high is loaded
- **WHEN** Deepy loads config for provider `deepseek` whose resolved reasoning mode is `high`
- **THEN** Deepy SHALL treat thinking as enabled
- **AND** it SHALL use `high` as the reasoning effort

#### Scenario: DeepSeek reasoning mode max is loaded
- **WHEN** Deepy loads config for provider `deepseek` whose resolved reasoning mode is `max`
- **THEN** Deepy SHALL treat thinking as enabled
- **AND** it SHALL use `max` as the reasoning effort

#### Scenario: Xiaomi switch-only thinking enabled is loaded
- **WHEN** Deepy loads config for provider `xiaomi`
- **AND** `model.thinking` resolves to true
- **THEN** Deepy SHALL expose thinking mode `enabled`
- **AND** it SHALL normalize the persisted reasoning effort to `enabled` when saving

#### Scenario: Xiaomi switch-only thinking disabled is loaded
- **WHEN** Deepy loads config for provider `xiaomi`
- **AND** `model.thinking` resolves to false
- **THEN** Deepy SHALL expose thinking mode `disabled`
- **AND** it SHALL normalize the persisted reasoning effort to `none` when saving

#### Scenario: OpenRouter boolean reasoning is loaded
- **WHEN** Deepy loads config for provider `openrouter`
- **AND** `model.thinking` resolves to true
- **AND** `model.reasoning_effort` is `enabled`
- **THEN** Deepy SHALL expose thinking mode `enabled`

#### Scenario: OpenRouter effort reasoning is loaded
- **WHEN** Deepy loads config for provider `openrouter`
- **AND** `model.reasoning_effort` is `xhigh`, `high`, `medium`, `low`, or `minimal`
- **THEN** Deepy SHALL expose that effort as the thinking mode

#### Scenario: Legacy thinking fields are loaded
- **WHEN** Deepy loads config that uses `model.thinking` and `model.reasoning_effort`
- **THEN** Deepy SHALL resolve `thinking = false` to disabled thinking
- **AND** it SHALL resolve `thinking = true` with `reasoning_effort = "high"` to enabled thinking
- **AND** it SHALL resolve `thinking = true` with `reasoning_effort = "max"` to DeepSeek reasoning mode `max` only for DeepSeek-style behavior

#### Scenario: Missing thinking fields are loaded
- **WHEN** Deepy loads config with no explicit thinking setting
- **THEN** Deepy SHALL use provider-specific default thinking
- **AND** DeepSeek SHALL default to reasoning mode `max`
- **AND** OpenRouter and Xiaomi MiMo SHALL default to thinking `enabled`

#### Scenario: Reasoning mode is saved
- **WHEN** Deepy saves DeepSeek reasoning mode `none`, `high`, or `max`
- **THEN** Deepy SHALL update existing `model.thinking` and `model.reasoning_effort` fields instead of requiring a new TOML field

#### Scenario: OpenRouter thinking mode is saved
- **WHEN** Deepy saves OpenRouter thinking mode `enabled`
- **THEN** it SHALL write `thinking = true` and `reasoning_effort = "enabled"`
- **WHEN** Deepy saves OpenRouter thinking mode `xhigh`, `high`, `medium`, `low`, or `minimal`
- **THEN** it SHALL write `thinking = true` and the selected effort to `reasoning_effort`
- **WHEN** Deepy saves OpenRouter thinking mode `disabled` or `none`
- **THEN** it SHALL write `thinking = false` and `reasoning_effort = "none"`

#### Scenario: Xiaomi switch-only thinking mode is saved
- **WHEN** Deepy saves Xiaomi MiMo thinking mode `enabled` or `disabled`
- **THEN** it SHALL write `thinking = true` and `reasoning_effort = "enabled"` for `enabled`
- **AND** it SHALL write `thinking = false` and `reasoning_effort = "none"` for `disabled`

### Requirement: Targeted Model Config Updates
Deepy SHALL update provider and model-related TOML settings without discarding
unrelated configuration.

#### Scenario: User saves model settings
- **WHEN** a user changes provider, model, or thinking mode through Deepy commands
- **THEN** Deepy SHALL persist the selected model settings to TOML
- **AND** it SHALL use existing `[model]` fields for provider, model name, base URL, thinking enabled state, and reasoning effort
- **AND** it SHALL preserve existing API key, context, logging, notify, tools, and UI theme settings
- **AND** the config file SHALL use permission mode `0600`

#### Scenario: Provider changes without explicit model
- **WHEN** a user changes provider without selecting a model
- **THEN** Deepy SHALL select that provider's default model
- **AND** it SHALL select that provider's default thinking mode
- **AND** it SHALL update the base URL to the provider default unless the user has explicitly overridden it in the same operation

#### Scenario: Config path is unknown
- **WHEN** a user attempts to save model settings and Deepy does not know the config path
- **THEN** Deepy SHALL report that the setting cannot be persisted
- **AND** it SHALL keep the current in-memory settings unchanged

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

### Requirement: Provider Selection Configuration
Deepy SHALL support an optional provider selection in TOML model configuration.

#### Scenario: Config has explicit provider
- **WHEN** Deepy loads config with `model.provider` set to `deepseek`, `openrouter`, or `xiaomi`
- **THEN** Deepy SHALL resolve that provider as the active provider
- **AND** it SHALL validate model and thinking choices against that provider's catalog

#### Scenario: Config has no provider and known base URL
- **WHEN** Deepy loads config without `model.provider`
- **AND** `model.base_url` points at official DeepSeek, OpenRouter, or Xiaomi MiMo hosts
- **THEN** Deepy SHALL infer `deepseek`, `openrouter`, or `xiaomi` respectively

#### Scenario: Config has no provider and unknown base URL
- **WHEN** Deepy loads config without `model.provider`
- **AND** `model.base_url` does not match a known provider host
- **THEN** Deepy SHALL preserve the existing DeepSeek-style behavior
- **AND** it SHALL NOT expose a separate user-facing compatibility provider

#### Scenario: Provider default base URLs are used
- **WHEN** Deepy writes provider-aware configuration without a user-specified base URL
- **THEN** it SHALL use `https://api.deepseek.com` for `deepseek`
- **AND** it SHALL use `https://openrouter.ai/api/v1` for `openrouter`
- **AND** it SHALL use `https://api.xiaomimimo.com/v1` for `xiaomi`

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

