## MODIFIED Requirements

### Requirement: Interactive Model Selection Command
Deepy SHALL provide a transactional provider/model/reasoning picker using saved provider profiles.

#### Scenario: User opens model picker
- **WHEN** a user runs /model
- **THEN** Deepy SHALL show the active provider, model and reasoning and offer DeepSeek, MiMo, Kimi and CLI Proxy
- **AND** DeepSeek SHALL be the default for new configurations

#### Scenario: User selects provider then model then thinking mode
- **WHEN** a user selects a provider
- **THEN** Deepy SHALL restore its saved selections or use defaults on first selection
- **AND** it SHALL offer only its catalog models and supported reasoning modes

#### Scenario: User completes model selection
- **WHEN** all selections complete and persistence succeeds
- **THEN** Deepy SHALL save the target profile and active selection without changing other profiles
- **AND** subsequent turns SHALL use the new selection and display a concise confirmation

#### Scenario: User cancels model selection
- **WHEN** the picker is cancelled or saving fails
- **THEN** Deepy SHALL keep previous persisted and runtime state

### Requirement: Direct Model Command Forms
Deepy SHALL support direct commands consistent with profile-aware model selection.

#### Scenario: User lists supported models
- **WHEN** a user runs /model list
- **THEN** Deepy SHALL group supported models by provider and show supported reasoning and image capabilities

#### Scenario: User sets DeepSeek model directly
- **WHEN** a user runs `/model set deepseek-flash` or `/model set mimo mimo-v2.5 enabled` or an equivalent supported provider/model command
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
- **WHEN** a user runs /model set mimo mimo-v2.5 enabled or /model set mimo mimo-v2.5-pro disabled
- **THEN** Deepy SHALL update the MiMo profile and active selection without changing other profiles

#### Scenario: User sets switch-only thinking directly
- **WHEN** a user runs /model thinking enabled or /model thinking disabled for MiMo
- **THEN** Deepy SHALL update the active profile reasoning while retaining its model

### Requirement: Persistent Interactive Status Footer
Deepy SHALL keep a compact interactive status footer fixed at the terminal
bottom during interactive prompt input and model or local-command work.

#### Scenario: Idle prompt is shown

- **WHEN** Deepy prompts for interactive user input
- **THEN** the prompt bottom footer SHALL show compact status segments for the
  active model and reasoning mode, CWD, and context window status
- **AND** the model and reasoning mode SHALL be represented as a single leading
  segment such as `model deepseek-flash[max]`
- **AND** the footer SHALL NOT show a separate `thinking` label segment for
  reasoning mode
- **AND** the footer SHALL NOT show persistent `Ctrl+D twice exit` help
- **AND** the footer SHALL show the newline hint `newline: ctrl+j`

#### Scenario: Model turn is running

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL reserve the bottom two terminal lines when the output
  stream is a TTY
- **AND** the last line SHALL keep the same compact status footer content and
  background style as the idle prompt footer
- **AND** the line above it SHALL show the realtime running status
- **AND** normal transcript output SHALL scroll above both reserved lines
- **AND** the realtime running status SHALL include working elapsed time, Esc
  interrupt guidance, and active work state
- **AND** the realtime running status SHALL include an animated spinner before
  the elapsed time while work is active
- **AND** the compact footer SHALL include model/reasoning, CWD, MCP status, and
  context window status
- **AND** the footer SHALL NOT be emitted as an ordinary transcript or
  scrollback status line
- **AND** the active work state SHALL use concise state labels such as
  `thinking` instead of reasoning transcript text or generated thinking
  summaries
- **AND** the footer SHALL NOT refresh on every thinking text delta
- **AND** spinner animation refreshes SHALL update only the reserved realtime
  status line
- **AND** working elapsed time and Esc interrupt guidance SHALL appear only in
  the reserved realtime status line, not in normal transcript output
- **AND** runtime status refreshes SHALL NOT interleave with transcript, tool
  result, diff, or shell output writes
- **AND** runtime status text SHALL be truncated and padded by terminal display
  cells so CJK and other wide-character tool details do not corrupt the row

#### Scenario: Local command is running

- **WHEN** Deepy runs an interactive local command submitted with `!`
- **THEN** Deepy SHALL reserve the bottom two terminal lines when the output
  stream is a TTY
- **AND** the last line SHALL keep the same compact status footer content and
  background style as the idle prompt footer
- **AND** the line above it SHALL show the realtime local-command status
- **AND** normal command output SHALL scroll above both reserved lines
- **AND** the realtime local-command status SHALL include working elapsed time,
  Esc interrupt guidance, local command running state, and the command text
- **AND** the realtime local-command status SHALL include an animated spinner
  before the elapsed time while the command is active
- **AND** the compact footer SHALL include CWD, MCP status, and context window
  status
- **AND** the footer SHALL NOT be emitted as an ordinary transcript or
  scrollback status line
- **AND** local-command runtime status refreshes SHALL NOT interleave with
  command output writes
- **AND** local-command runtime status text SHALL be truncated and padded by
  terminal display cells
