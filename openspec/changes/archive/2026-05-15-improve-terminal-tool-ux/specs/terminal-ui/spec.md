## ADDED Requirements

### Requirement: Unified Tool Activity Display

Deepy SHALL render all terminal-visible tool activity using a consistent
user-facing tool label style while preserving underlying tool protocol names.

#### Scenario: Tool call is streamed

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

#### Scenario: Session history is rendered

- **WHEN** Deepy renders previous session history containing tool calls or tool
  outputs
- **THEN** the history output SHALL use the same display label convention as live
  streamed output

### Requirement: Unified Write And Edit Preview Headers

Deepy SHALL render file-change preview headers as tool activity rather than as a
separate `Wrote` or `Edited` display style.

#### Scenario: Write preview is rendered

- **WHEN** a successful write result includes a diff preview
- **THEN** Deepy SHALL render the preview header with the same display label
  convention used for tool activity
- **AND** the header SHALL include the changed path when available
- **AND** the header SHALL include added and removed line counts
- **AND** the header SHALL NOT lead with a standalone `Wrote` label

#### Scenario: Modify preview is rendered

- **WHEN** a successful modify or edit result includes a diff preview
- **THEN** Deepy SHALL render the preview header with the same display label
  convention used for tool activity
- **AND** the header SHALL include the changed path when available
- **AND** the header SHALL include added and removed line counts
- **AND** the header SHALL NOT lead with a standalone `Edited` label

## MODIFIED Requirements

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL print complete thinking text immediately when it is
received.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a working status with elapsed time
- **AND** it SHALL show useful thinking/progress summaries when available
- **AND** thinking transcript output SHALL use the same bracketed label family as
  tool activity

#### Scenario: Thinking delta is received

- **WHEN** Deepy receives thinking text for a model turn
- **THEN** Deepy SHALL immediately print that thinking text to normal transcript
  output
- **AND** it SHALL print a visible `[Thinking]` label for the thinking block
- **AND** it SHALL NOT apply summary truncation to the thinking text
- **AND** it SHALL preserve readable line breaks in the printed thinking text

### Requirement: Clarification Prompt Display

Deepy SHALL keep AskUserQuestion interaction readable by hiding internal tool
protocol details from normal terminal output and by presenting custom answers as
an explicit user-facing option.

#### Scenario: AskUserQuestion tool call is streamed

- **WHEN** Deepy renders a streamed AskUserQuestion tool call
- **THEN** the terminal output SHALL NOT include the raw `questions` argument JSON
- **AND** it SHALL show only a concise AskUserQuestion progress label using the
  same display label style as other tools

#### Scenario: AskUserQuestion history is rendered

- **WHEN** Deepy renders session history containing an AskUserQuestion tool call
- **THEN** the history output SHALL NOT include the raw `questions` argument JSON
- **AND** it SHALL preserve a concise indication that AskUserQuestion was used
- **AND** it SHALL use the same display label style as other tools

#### Scenario: Clarification options are displayed

- **WHEN** Deepy displays AskUserQuestion options to the user
- **THEN** it SHALL include a clearly labeled custom-answer option
- **AND** the custom-answer label SHALL be understandable in the question's
  language when the question language is clear
- **AND** the prompt SHALL make clear that selecting or typing the custom-answer
  option allows free-form text

#### Scenario: User answers clarification questions

- **WHEN** Deepy sends formatted AskUserQuestion answers back to the model
- **THEN** the answer message SHALL include the selected or custom answer text
- **AND** it SHALL NOT include internal option sentinel names in normal
  user-facing output
