## ADDED Requirements

### Requirement: Modern UI Surface Polish
The Modern UI SHALL keep conversation transcript content separate from transient interaction controls and SHALL present management surfaces with compact, readable layouts.

#### Scenario: Classic and Modern UI are peer system UIs
- **WHEN** Deepy describes terminal UI choices
- **THEN** the Rich/prompt-toolkit UI SHALL be called `Classic UI`
- **AND** the Textual UI SHALL be called `Modern UI`
- **AND** Modern UI SHALL NOT be described as experimental

#### Scenario: Light theme resolves to Solarized Light
- **WHEN** the Modern UI starts with the shared `light` UI theme and no explicit Textual theme override
- **THEN** it SHALL use `solarized-light` as the Textual theme

#### Scenario: Prompt footer shows concise interrupt hint
- **WHEN** the prompt action hint is rendered
- **THEN** it SHALL show `Esc interrupt`
- **AND** it SHALL NOT show `Ctrl+C interrupt`

#### Scenario: Transcript content is selectable
- **WHEN** conversation content is rendered in the transcript
- **THEN** the TUI SHALL NOT capture terminal mouse selection
- **AND** it SHALL NOT bind `Ctrl+C` or `Cmd+C` to app-level copy or interrupt actions

#### Scenario: Reasoning transcript uses compact styling
- **WHEN** reasoning or thinking content is shown in the transcript
- **THEN** it SHALL use the same compact role-line layout as other transcript blocks
- **AND** it SHALL avoid rendering a large standalone `Thinking` title

#### Scenario: Choices use bottom interaction sheet
- **WHEN** the user opens a transient choice flow such as theme, model, session, audit, or ask-user-question selection
- **THEN** the choice controls SHALL appear in a bottom interaction surface near the prompt
- **AND** selecting or cancelling the choice SHALL NOT append decision-result text to the transcript

#### Scenario: Skill management uses compact differentiated rows
- **WHEN** the user opens the skill management surface
- **THEN** installed and market tabs SHALL be visibly presented as tabs
- **AND** each skill SHALL render as a single row with name, state/source metadata, and a truncated description
- **AND** skill rows SHALL keep long descriptions on one visual line by truncating overflow
- **AND** skill rows SHALL use the available management surface width before truncating descriptions
- **AND** installed, market, built-in, and updateable states SHALL be visually distinguishable
- **AND** market rows SHALL show installed state without showing version numbers
- **AND** installed rows SHALL show whether each skill is installed in user or project scope

#### Scenario: Skill market loading is asynchronous
- **WHEN** the user opens or refreshes the skill management surface
- **THEN** the surface SHALL appear immediately with a loading state while market HTTP data is fetched
- **AND** the TUI SHALL update the existing surface when market data or errors are available
- **WHEN** the user installs or uninstalls a skill from the skill management surface
- **THEN** the surface SHALL show an operation loading state while the action is running
- **AND** the surface SHALL refresh in place after the action completes

#### Scenario: Skill management actions stay in the management flow
- **WHEN** the user installs or uninstalls a skill from the skill management surface
- **THEN** the TUI SHALL refresh the skill management surface
- **AND** it SHALL NOT append install or uninstall result text to the transcript
- **WHEN** the user presses Enter on an uninstalled market skill
- **THEN** the TUI SHALL show skill detail
- **WHEN** the user presses `i` on an uninstalled market skill
- **THEN** the TUI SHALL ask for the install scope before installing
- **WHEN** the user presses Enter or `v` on an installed skill row
- **THEN** the TUI SHALL show skill detail instead of loading the skill into the conversation

#### Scenario: Status and configuration information is grouped
- **WHEN** the user opens status or configuration information from the Modern UI
- **THEN** the information SHALL be grouped into concise sections for model, runtime, project, MCP, session, and UI where applicable
- **AND** it SHALL avoid dumping broad mixed markdown when compact grouped data is available

#### Scenario: MCP command prints current runtime tools
- **WHEN** the user runs `/mcp` in Modern UI
- **THEN** the TUI SHALL append the current MCP server and tool status to the transcript
- **AND** it SHALL use the same MCP status formatter as Classic UI
- **AND** it SHALL NOT open an MCP configuration modal

#### Scenario: Local command output is visible
- **WHEN** the user submits a local command with `!<command>` in Modern UI
- **THEN** the TUI SHALL append the command result to the transcript as a visible shell output block
- **AND** the block SHALL show the command output without requiring an expand action
- **AND** the block SHALL include concise execution metadata such as exit status and duration
- **AND** regular model tool calls SHALL remain compact unless they are user local command results

### Requirement: Configured UI Routing
Deepy SHALL persist the default system UI and route the default interactive command through that setting.

#### Scenario: Missing UI config defaults to Classic dark
- **WHEN** no UI interface or theme is configured
- **THEN** Deepy SHALL default to `classic` interface and `dark` theme

#### Scenario: Default command uses configured UI
- **WHEN** the user starts `deepy`
- **THEN** Deepy SHALL start Classic UI when `ui.interface` is `classic`
- **AND** Deepy SHALL start Modern UI when `ui.interface` is `modern`
- **AND** `deepy tui` SHALL remain available as a Modern UI compatibility command

#### Scenario: Slash command persists UI choice
- **WHEN** the user runs `/ui classic` or `/ui modern`
- **THEN** Deepy SHALL persist the selected `ui.interface`
- **AND** it SHALL tell the user that the selected UI applies on restart

#### Scenario: Reset setup offers UI and theme combinations
- **WHEN** the user resets or interactively sets up config
- **THEN** the UI selection SHALL offer Classic UI + dark theme, Classic UI + light theme, Modern UI + dark theme, and Modern UI + light theme
- **AND** the first option SHALL be Classic UI + dark theme
