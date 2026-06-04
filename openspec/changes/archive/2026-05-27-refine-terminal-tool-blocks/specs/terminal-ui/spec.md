## MODIFIED Requirements

### Requirement: Startup Screen
Deepy SHALL show a compact welcome panel.

#### Scenario: User starts interactive mode

- **WHEN** Deepy starts
- **THEN** the welcome panel SHALL show the Deepy identity, version, provider,
  model, thinking settings, CWD, active UI theme, and only core commands
- **AND** the welcome panel SHALL prefer a wide layout with enough vertical
  spacing for readable grouped content when terminal width allows
- **AND** the welcome panel SHALL include a compact Deepy logo or equivalent
  identity mark
- **AND** the welcome panel SHALL show a concise product description near the
  Deepy identity
- **AND** the welcome panel SHALL avoid duplicating startup information across
  multiple large vertical sections
- **AND** the welcome panel SHALL group startup metadata under a `Session`
  heading
- **AND** the welcome panel SHALL group common commands under a `Commands`
  heading
- **AND** core command entries SHALL render one command per line in a consistent
  label-and-description style

#### Scenario: First interactive startup has no saved theme

- **WHEN** Deepy starts interactive mode and no valid UI theme is saved
- **THEN** Deepy SHALL show numbered `dark` and `light` theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL persist the choice before rendering the welcome panel
- **AND** the welcome panel SHALL use the selected theme

### Requirement: Unified Tool Activity Display

Deepy SHALL render tool calls and tool outputs with concise, consistent labels.

#### Scenario: Tool call is rendered

- **WHEN** Deepy renders a streamed tool call for any built-in tool
- **THEN** the first visible tool token SHALL use a normalized display label
- **AND** the display label SHALL have one shared prominent visual treatment for
  all tools
- **AND** the display label SHALL NOT use different colors to distinguish
  different tools
- **AND** built-in tool labels SHALL use a consistent bracketed tool-name style
  such as `[WebFetch]`, `[Write]`, `[Modify]`, and `[Read]`
- **AND** the tool parameters SHALL remain visually secondary to the tool label

#### Scenario: Tool output is rendered

- **WHEN** Deepy renders a tool output status line
- **THEN** the status line SHALL use the same normalized display label and shared
  prominent visual treatment used for tool calls
- **AND** success, failure, and waiting state styling MAY still use status colors
  independent of the tool label

#### Scenario: Shell output is rendered

- **WHEN** Deepy renders a shell tool result with stdout or stderr output
- **THEN** Deepy SHALL show the full captured shell output available in the tool
  result
- **AND** the shell output SHALL use a distinct terminal style from ordinary tool
  status lines
- **AND** the shell output SHALL remain associated with the `[Shell]` tool result
- **AND** the shell output detail block SHALL use the available terminal width
  instead of shrinking to content width
- **AND** the shell output detail block SHALL NOT repeat a titled `[Shell]` or
  `Shell` panel header after the status line

#### Scenario: Session history is rendered

- **WHEN** Deepy renders previous session history containing tool calls or tool
  outputs
- **THEN** the history output SHALL use the same display label convention as live
  streamed output
- **AND** shell detail output in history SHALL use the same lightweight block
  layout as live shell output

### Requirement: Todo Board Rendering

Deepy SHALL render the active todo plan as a compact terminal board instead of
raw tool JSON.

#### Scenario: Todo plan is created or updated

- **WHEN** a `todo_write` result updates the current todo plan
- **THEN** Deepy SHALL render a terminal todo board containing the current
  progress count and task list
- **AND** the board SHALL show pending, in-progress, and completed statuses with
  distinct visual markers
- **AND** the board SHALL use the active terminal theme palette for readable
  dark and light background output
- **AND** the board SHALL use the available terminal width instead of shrinking
  to content width

#### Scenario: Todo board summary is rendered

- **WHEN** the todo board is rendered for a non-empty todo plan
- **THEN** Deepy SHALL show the number of completed items and total items
- **AND** it SHALL show the current `in_progress` item when one exists
- **AND** it SHALL fall back to the first pending item when no item is marked
  `in_progress`
- **AND** it SHALL NOT duplicate runtime footer details such as model, context,
  elapsed time, or interrupt hints

#### Scenario: Todo board is rendered in a narrow terminal

- **WHEN** the terminal width or height cannot fit the complete todo board
- **THEN** Deepy SHALL truncate or compact the board without breaking table or
  block layout
- **AND** it SHALL preserve the progress count and current-task summary

#### Scenario: Todo tool output appears in history

- **WHEN** Deepy renders session history containing todo updates
- **THEN** it SHALL render the latest relevant todo state as a readable board or
  compact progress summary
- **AND** it SHALL NOT replay verbose raw todo JSON as ordinary transcript text
- **AND** todo detail output in history SHALL use the same compact block layout
  as live todo output
