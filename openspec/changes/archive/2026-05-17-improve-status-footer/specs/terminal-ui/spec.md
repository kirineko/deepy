## ADDED Requirements

### Requirement: Persistent Interactive Status Footer

Deepy SHALL keep a compact interactive status footer fixed at the terminal bottom during interactive prompt input and model or local-command work.

#### Scenario: Idle prompt is shown

- **WHEN** Deepy prompts for interactive user input
- **THEN** the prompt bottom footer SHALL show compact status segments for the active model and reasoning mode, CWD, and context window status
- **AND** the model and reasoning mode SHALL be represented as a single leading segment such as `model deepseek-v4-pro[max]`
- **AND** the footer SHALL NOT show a separate `thinking` label segment for reasoning mode
- **AND** the footer SHALL NOT show persistent `Ctrl+D twice exit` help
- **AND** the footer SHALL show the newline hint `newline: ctrl+j`

#### Scenario: Model turn is running

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL reserve the bottom two terminal lines when the output stream is a TTY
- **AND** the last line SHALL keep the same compact status footer content and background style as the idle prompt footer
- **AND** the line above it SHALL show the realtime running status
- **AND** normal transcript output SHALL scroll above both reserved lines
- **AND** the realtime running status SHALL include working elapsed time, Esc interrupt guidance, and active work state
- **AND** the realtime running status SHALL include an animated spinner before the elapsed time while work is active
- **AND** the compact footer SHALL include model/reasoning, CWD, MCP status, and context window status
- **AND** the footer SHALL NOT be emitted as an ordinary transcript or scrollback status line
- **AND** the active work state SHALL use concise state labels such as `thinking` instead of reasoning transcript text or generated thinking summaries
- **AND** the footer SHALL NOT refresh on every thinking text delta
- **AND** spinner animation refreshes SHALL update only the reserved realtime status line
- **AND** working elapsed time and Esc interrupt guidance SHALL appear only in the reserved realtime status line, not in normal transcript output

#### Scenario: Local command is running

- **WHEN** Deepy runs an interactive local command submitted with `!`
- **THEN** Deepy SHALL reserve the bottom two terminal lines when the output stream is a TTY
- **AND** the last line SHALL keep the same compact status footer content and background style as the idle prompt footer
- **AND** the line above it SHALL show the realtime local-command status
- **AND** normal command output SHALL scroll above both reserved lines
- **AND** the realtime local-command status SHALL include working elapsed time, Esc interrupt guidance, local command running state, and the command text
- **AND** the realtime local-command status SHALL include an animated spinner before the elapsed time while the command is active
- **AND** the compact footer SHALL include CWD, MCP status, and context window status
- **AND** the footer SHALL NOT be emitted as an ordinary transcript or scrollback status line
- **AND** it SHALL NOT send that command to the model

### Requirement: Interactive Status Footer Visual Hierarchy

Deepy SHALL render the interactive status footer with theme-aware visual hierarchy instead of treating all segments as one undifferentiated text style.

#### Scenario: Footer is rendered in a dark theme

- **WHEN** the active UI theme resolves to `dark`
- **THEN** the footer SHALL use one coordinated foreground color family for model identity, active-work state, loaded indicators, and muted metadata
- **AND** separators SHALL use a lower-contrast color from the same theme
- **AND** the footer SHALL NOT render unrelated bright accent color blocks across adjacent segments
- **AND** all footer text SHALL remain readable on the dark toolbar background

#### Scenario: Footer is rendered in a light theme

- **WHEN** the active UI theme resolves to `light`
- **THEN** the footer SHALL use one coordinated foreground color family for model identity, active-work state, loaded indicators, and muted metadata
- **AND** separators SHALL use a lower-contrast color from the same theme
- **AND** the footer SHALL NOT render unrelated bright accent color blocks across adjacent segments
- **AND** all footer text SHALL remain readable on the light toolbar background
- **AND** the running compact footer row SHALL use the same toolbar background color as the completed prompt footer row
- **AND** the running compact footer row SHALL preserve segment emphasis such as bold model identity from the completed prompt footer row

#### Scenario: Footer segment casing is rendered

- **WHEN** Deepy builds footer segment labels other than case-sensitive file names
- **THEN** footer status keys SHALL use a consistent lowercase style
- **AND** case-sensitive file names such as `AGENTS.md` SHALL preserve their exact casing
- **AND** footer title keys `model`, `cwd`, `mcp`, `ctx`, and `newline` SHALL be bold while their values remain normal weight
- **AND** the loaded indicator `[AGENTS.md]` SHALL be bold

## MODIFIED Requirements

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL print complete thinking text immediately when it is
received.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a working status with elapsed time
- **AND** it SHALL show useful thinking/progress summaries when available
- **AND** the working status SHALL preserve the compact interactive status footer instead of replacing it with an unrelated status surface
- **AND** in a TTY, the working status footer SHALL be rendered on a reserved terminal-bottom line instead of a normal Rich status line
- **AND** the working status footer SHALL NOT include thinking transcript text or thinking summaries
- **AND** thinking transcript output SHALL use the same bracketed label family as
  tool activity

#### Scenario: Thinking delta is received

- **WHEN** Deepy receives thinking text for a model turn
- **THEN** Deepy SHALL immediately stream that thinking text to normal transcript output without waiting for a buffer-size threshold
- **AND** it SHALL print a visible `[Thinking]` label for the thinking block
- **AND** it SHALL NOT apply summary truncation to the thinking text
- **AND** it SHALL preserve readable line breaks in the printed thinking text
- **AND** it SHALL update the footer to a concise `thinking` state at most once per continuous thinking block

### Requirement: Bottom Context Status Accuracy

Deepy's interactive status footer SHALL show Cline-style Context Window usage without a separate compaction pressure token segment.

#### Scenario: Latest request usage is known

- **WHEN** a model request completes with usable token usage
- **THEN** the footer SHALL show Context Window usage based on the latest request context occupancy
- **AND** it SHALL use a compact `ctx` label for that segment
- **AND** it SHALL show the configured context window as the total
- **AND** it SHALL show the percentage as latest request context occupancy divided by the configured context window
- **AND** it SHALL NOT show a separate `compact` token pressure segment
- **AND** it SHALL NOT use the redundant label `ctx win`

#### Scenario: Latest turn is short

- **WHEN** a session has existing context and the user sends a short follow-up prompt
- **THEN** the footer Context Window usage SHALL reflect the latest request occupancy even when it is lower than the previous request
- **AND** it SHALL NOT show the previous effective session pressure as a second compact value

#### Scenario: Context state is near compaction threshold

- **WHEN** latest request Context Window used tokens are at or above the configured compact threshold
- **THEN** the footer SHALL append a concise `compact next` hint to the `ctx` segment
- **AND** it SHALL NOT show a separate compaction pressure token count

#### Scenario: Explicit compaction reduces context

- **WHEN** manual or automatic compaction rewrites the active session
- **THEN** Context Window usage SHALL update to the compacted replacement history checkpoint
- **AND** the footer SHALL NOT show a separate compacted-history pressure value
- **AND** the compaction success message SHALL use the pre-compaction Context Window used value as its before token count when available

### Requirement: MCP Runtime Status

Deepy SHALL surface MCP availability without overwhelming normal chat output.

#### Scenario: Startup screen is shown

- **WHEN** Deepy starts interactive mode
- **AND** MCP is enabled
- **THEN** the welcome or status surface SHALL show a concise MCP availability
  summary

#### Scenario: Bottom toolbar is shown

- **WHEN** MCP servers are active in an interactive session
- **THEN** the interactive status footer SHALL include the exact compact indicator `mcp N`, where `N` is the number of active MCP servers
- **AND** the indicator SHALL use lowercase `mcp`
- **AND** the indicator SHALL NOT replace context window usage or AGENTS.md
  status information
