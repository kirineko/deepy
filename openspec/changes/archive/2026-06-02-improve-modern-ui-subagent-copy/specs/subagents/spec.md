## MODIFIED Requirements

### Requirement: Subagent Lifecycle Visibility

Deepy SHALL show users when subagents are assigned and what they return.

#### Scenario: Subagent starts

- **WHEN** the main agent invokes a subagent
- **THEN** Deepy SHALL render a visible subagent-start event
- **AND** the event SHALL include the subagent name and concise task description

#### Scenario: Subagent completes

- **WHEN** a subagent completes successfully
- **THEN** Deepy SHALL render a visible subagent-completed event
- **AND** the event SHALL include a concise result summary
- **AND** rich transcript UIs SHALL provide a way to expand the subagent event and inspect the returned report without requiring the main assistant to repeat it

#### Scenario: Subagent fails

- **WHEN** a subagent fails, times out, or is blocked
- **THEN** Deepy SHALL render a visible subagent failure or blocked event
- **AND** the main agent SHALL retain control and decide how to proceed

#### Scenario: Subagent generates verbose nested output

- **WHEN** a subagent emits nested thinking, tool calls, or progress output
- **THEN** Deepy SHALL keep the main transcript readable
- **AND** it SHALL avoid flooding the main assistant response with raw nested
  output unless the user explicitly asks for details
- **AND** rich transcript UIs MAY show bounded progress or returned-report detail inside an explicit subagent expansion surface
