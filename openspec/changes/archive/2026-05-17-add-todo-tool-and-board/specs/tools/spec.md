## ADDED Requirements

### Requirement: Todo Write Tool

Deepy SHALL expose a built-in `todo_write` tool for maintaining the active
session todo plan.

#### Scenario: Function tools are registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL register a `todo_write` FunctionTool through the OpenAI
  Agents SDK tool flow
- **AND** the tool schema SHALL accept a complete list of todo items containing
  `id`, `content`, and `status`

#### Scenario: Valid todo list is written

- **WHEN** the model invokes `todo_write` with a valid todo list
- **THEN** Deepy SHALL update the active session todo plan
- **AND** the tool result SHALL include structured metadata identifying the
  result as a todo-list update
- **AND** the tool result SHALL include enough metadata for the terminal UI to
  render the current board without parsing raw prose

#### Scenario: Todo list is read

- **WHEN** the model invokes `todo_write` without a `todos` list
- **THEN** Deepy MAY return the current todo plan without modifying it
- **AND** the read result SHALL NOT create a duplicate board update when the
  todo state has not changed

#### Scenario: Invalid todo list is rejected

- **WHEN** the model invokes `todo_write` with duplicate ids, empty content,
  unsupported statuses, or multiple `in_progress` items
- **THEN** Deepy SHALL return a structured tool failure
- **AND** it SHALL leave the previous valid todo plan unchanged

#### Scenario: Todo tool output is displayed

- **WHEN** Deepy formats a `todo_write` tool call or result for terminal output
- **THEN** it SHALL use the same normalized tool label convention as other
  built-in tools
- **AND** it SHALL NOT show raw todo JSON as the primary user-facing display
