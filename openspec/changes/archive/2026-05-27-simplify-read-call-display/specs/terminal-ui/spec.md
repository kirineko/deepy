## MODIFIED Requirements

### Requirement: Unified Tool Activity Display

Deepy SHALL render tool calls and tool outputs with concise, consistent labels.

#### Scenario: Read tool call parameters use concise paths

- **WHEN** Deepy renders a streamed `Read` tool call with one or more path
  arguments
- **THEN** the first visible tool token SHALL show the normalized `[Read]`
  display label followed by the requested paths
- **AND** paths under the current project root SHALL be displayed relative to
  that project root
- **AND** the parameter text SHALL NOT expose JSON object keys, list brackets,
  or absolute project-root-prefixed paths when path values can be extracted
