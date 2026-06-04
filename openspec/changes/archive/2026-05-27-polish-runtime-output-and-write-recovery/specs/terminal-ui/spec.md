## MODIFIED Requirements

### Requirement: Markdown Rendering
Deepy SHALL render assistant Markdown as formatted terminal output.

#### Scenario: Assistant returns Markdown

- **WHEN** assistant output contains headings, lists, code blocks, links, or
  inline emphasis
- **THEN** Deepy SHALL render it through the Markdown UI path instead of printing
  raw Markdown syntax
- **AND** fenced code blocks SHALL render as visually distinct terminal code
  blocks rather than visible raw fence markers or plain paragraph text
- **AND** fenced code blocks with a recognized language tag SHOULD include
  syntax-highlighted token styling

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL render thinking text according to the active UI view mode
when it is received.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a one-line runtime working status with elapsed time
- **AND** it SHALL show the current-turn cumulative stream token estimate when
  available
- **AND** it SHALL show a concise current activity state before the interrupt
  hint, such as `Thinking`, `Write`, `WebFetch`, or `MCP`
- **AND** tool activity state SHALL show only the tool display name and SHALL
  NOT include tool arguments or parameter payloads
- **AND** the visible order SHALL be elapsed time, token estimate when present,
  current activity state when present, and `esc to interrupt`
- **AND** high-frequency stream deltas SHALL NOT repaint the inline runtime
  status more often than needed for smooth terminal rendering
