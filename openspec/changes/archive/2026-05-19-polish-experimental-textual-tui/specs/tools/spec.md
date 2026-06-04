## ADDED Requirements

### Requirement: Textual Tool Result Surfaces
Deepy SHALL render built-in tool results in the experimental Textual TUI through
tool-specific readable surfaces while preserving existing model-facing tool
names and result JSON.

#### Scenario: Shell tool result is rendered in TUI
- **WHEN** the `shell` tool emits output in the experimental TUI
- **THEN** the TUI SHALL show command, cwd when known, exit code, status,
  duration when known, stdout, stderr, and truncation state in a shell-specific
  block
- **AND** failed, timed-out, or interrupted commands SHALL be visually
  distinguishable from successful commands

#### Scenario: Read tool result is rendered in TUI
- **WHEN** the `read` tool emits file content in the experimental TUI
- **THEN** the TUI SHALL show file path, line range or page range when known,
  and a readable preview
- **AND** large content SHALL be folded, truncated, or expanded through a
  deliberate interaction rather than dumped directly into the transcript

#### Scenario: Todo tool result is rendered in TUI
- **WHEN** the `todo_write` tool updates or reads todos in the experimental TUI
- **THEN** the TUI SHALL show a concise transcript summary
- **AND** it SHALL project the current todo list into a side panel or dedicated
  view when that surface is visible

#### Scenario: Web tool result is rendered in TUI
- **WHEN** `WebSearch` or `WebFetch` emits output in the experimental TUI
- **THEN** the TUI SHALL show source or URL metadata when available
- **AND** result bodies SHALL be expandable when they are too large for a
  concise transcript block

#### Scenario: MCP tool result is rendered in TUI
- **WHEN** an MCP-backed tool emits output or status metadata in the
  experimental TUI
- **THEN** the TUI SHALL identify the MCP server or tool when known
- **AND** it SHALL show success, failure, cleanup, or unavailable state without
  exposing raw internal tracebacks as the primary display

### Requirement: Textual Waiting-For-User Tool State
Deepy SHALL render tool results that require user input as an explicit waiting
state in the experimental Textual TUI.

#### Scenario: Tool result awaits user response
- **WHEN** a tool result contains `awaitUserResponse=true`
- **THEN** the TUI SHALL render the tool block as waiting for user input
- **AND** it SHALL expose the corresponding interactive surface when metadata
  identifies a supported waiting state

#### Scenario: AskUserQuestion awaits user response
- **WHEN** an AskUserQuestion result is rendered in the experimental TUI
- **THEN** the TUI SHALL show normalized questions and options
- **AND** it SHALL support a custom-answer path when provided by the question
  contract
- **AND** selected answers SHALL be visible in transcript history

### Requirement: Textual Tool Block Expansion
Deepy SHALL make large or detailed tool output expandable in the experimental
Textual TUI.

#### Scenario: Tool output has hidden details
- **WHEN** a TUI tool block contains details beyond its concise summary
- **THEN** the user SHALL be able to expand and collapse the block by keyboard
  and pointer interaction
- **AND** the expanded content SHALL remain within the tool block or a
  dedicated detail surface without overlapping transcript content

#### Scenario: Tool output is short and successful
- **WHEN** a successful tool output is short enough to read inline
- **THEN** the TUI MAY show the output directly in the concise block
- **AND** it SHALL still preserve a consistent title and status shape across
  tool types
