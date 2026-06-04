## MODIFIED Requirements

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

#### Scenario: Subagent completes with report about rejected approval

- **WHEN** a subagent completes successfully
- **AND** its structured report text mentions an audit approval rejection
- **THEN** the terminal UI SHALL render the subagent as successful
- **AND** it SHALL NOT render the subagent lifecycle line as rejected solely because of report text

#### Scenario: Subagent needs approval

- **WHEN** a subagent reaches a command approval-required state
- **THEN** the terminal UI SHALL preserve the approval question flow
- **AND** it SHALL show the command and policy reason clearly enough for the user
  to decide

#### Scenario: Subagent fails

- **WHEN** a subagent fails, times out, or is blocked
- **THEN** the terminal UI SHALL render a concise failure or blocked line
- **AND** the active Deepy session SHALL remain usable
