## MODIFIED Requirements

### Requirement: Subagent Tool Boundaries

Deepy SHALL give subagents explicit bounded tool sets instead of inheriting all
main-agent tools.

#### Scenario: Subagent tools are built

- **WHEN** Deepy constructs a subagent
- **THEN** Deepy SHALL derive the subagent's tools from the subagent definition
  and Deepy's supported subagent tool policy
- **AND** it SHALL support v3 file tool names such as `Read` for read-oriented
  subagents
- **AND** it SHALL exclude unsupported, removed, or forbidden tools before
  exposing the subagent to the main agent
- **AND** unsupported removed file tools such as `read_file`, `edit_text`,
  `write_file`, and `apply_patch` SHALL cause custom subagent definitions to be
  rejected with a concise diagnostic

#### Scenario: Subagent attempts nested delegation

- **WHEN** a subagent attempts to create or call another subagent
- **THEN** Deepy SHALL prevent nested subagent spawning
- **AND** it SHALL return a clear unavailable-tool result or omit subagent tools
  from the subagent's tool set

#### Scenario: Built-in subagent completes

- **WHEN** a built-in or custom subagent finishes successfully
- **THEN** it SHALL return a concise report to the main agent
- **AND** the report SHALL include the assigned scope, key findings or actions,
  relevant file paths when applicable, command results when applicable, and any
  unresolved issues
