## ADDED Requirements

### Requirement: Subagent Lifecycle Rendering

Deepy's stable terminal UI SHALL render subagent lifecycle events clearly and
compactly.

#### Scenario: Subagent starts

- **WHEN** a subagent starts during a model turn
- **THEN** the terminal UI SHALL render a concise subagent start line
- **AND** the line SHALL include the subagent name and assigned task summary

#### Scenario: Subagent completes

- **WHEN** a subagent completes during a model turn
- **THEN** the terminal UI SHALL render a concise completion line
- **AND** the line SHALL include a readable result summary

#### Scenario: Subagent needs approval

- **WHEN** a subagent reaches a command approval-required state
- **THEN** the terminal UI SHALL preserve the approval question flow
- **AND** it SHALL show the command and policy reason clearly enough for the user
  to decide

#### Scenario: Subagent fails

- **WHEN** a subagent fails, times out, or is blocked
- **THEN** the terminal UI SHALL render a concise failure or blocked line
- **AND** the active Deepy session SHALL remain usable

### Requirement: Subagent Output Non-Interference

Deepy's stable terminal UI SHALL keep subagent output from corrupting main-agent
thinking and response rendering.

#### Scenario: Subagent emits nested output

- **WHEN** a subagent emits nested thinking, tool calls, or raw output
- **THEN** the terminal UI SHALL keep the main transcript readable
- **AND** it SHALL avoid interleaving raw nested output into the main assistant
  response

#### Scenario: User requests details

- **WHEN** the user asks for subagent details or the main agent needs to cite a
  subagent result
- **THEN** Deepy MAY show or summarize the relevant subagent details
- **AND** it SHALL preserve the concise lifecycle summary in the normal
  transcript
