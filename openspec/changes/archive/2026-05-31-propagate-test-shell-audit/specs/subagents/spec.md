## MODIFIED Requirements

### Requirement: Subagent Audit Propagation

Deepy SHALL preserve system audit mode enforcement for tool calls made from
subagents.

#### Scenario: Subagent built-in tool requires approval

- **WHEN** a subagent invokes a built-in side-effect tool that requires approval
  under the active audit mode
- **THEN** Deepy SHALL surface the SDK approval interruption to the outer Deepy
  session
- **AND** the user SHALL resolve the approval in the outer session UI

#### Scenario: Tester subagent command requires approval

- **WHEN** the tester subagent invokes `test_shell` with a command classified as
  medium-risk `approval_required`
- **AND** the active audit mode requires command approval
- **THEN** Deepy SHALL surface the SDK approval interruption to the outer Deepy
  session
- **AND** the pending approval SHALL include the `test_shell` tool name and exact
  command arguments
- **AND** approval SHALL resume the original top-level run and execute through
  the constrained `test_shell` path

#### Scenario: Tester subagent command is auto-approved

- **WHEN** the tester subagent invokes `test_shell` with a command classified as
  medium-risk `approval_required`
- **AND** the active audit mode auto-approves command execution
- **THEN** Deepy SHALL execute the command through the constrained `test_shell`
  path without requiring the main agent to rerun it through raw `shell`

#### Scenario: Subagent MCP tool requires approval

- **WHEN** a subagent invokes an MCP tool that requires approval under the active
  audit mode
- **THEN** Deepy SHALL surface the SDK approval interruption to the outer Deepy
  session
- **AND** the approval prompt SHALL identify the subagent context when that
  context is available from the SDK interruption

#### Scenario: Subagent approval is resolved

- **WHEN** the user approves or rejects a subagent-originated approval
- **THEN** Deepy SHALL resolve the interruption on the original top-level SDK run
  state
- **AND** Deepy SHALL resume the original top-level run rather than starting a
  new subagent run
