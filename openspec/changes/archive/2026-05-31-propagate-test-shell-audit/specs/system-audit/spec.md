## MODIFIED Requirements

### Requirement: Audit Modes

Deepy SHALL provide a system audit mode that controls whether model-requested
side-effecting actions require user approval before execution.

#### Scenario: Normal mode requires approval for side effects

- **WHEN** the active audit mode is `normal`
- **AND** the model requests a managed text write, shell command execution,
  medium-risk constrained `test_shell` command execution, background task
  termination, or MCP tool call
- **THEN** Deepy SHALL require user approval before executing the requested
  action

#### Scenario: Auto mode approves managed text writes

- **WHEN** the active audit mode is `auto`
- **AND** the model requests `Write` or `Update`
- **THEN** Deepy SHALL allow the managed text write to proceed without a user
  approval prompt
- **AND** Deepy SHALL still apply existing text mutation guardrails before
  committing the write

#### Scenario: Auto mode keeps command approval

- **WHEN** the active audit mode is `auto`
- **AND** the model requests shell command execution, medium-risk constrained
  `test_shell` command execution, or background task termination
- **THEN** Deepy SHALL require user approval before executing the requested
  action

#### Scenario: Yolo mode auto-approves side effects

- **WHEN** the active audit mode is `yolo`
- **AND** the model requests a managed text write, shell command execution,
  medium-risk constrained `test_shell` command execution, background task
  termination, or MCP tool call
- **THEN** Deepy SHALL allow the requested action to proceed without a user
  approval prompt
- **AND** Deepy SHALL still apply hard safety guardrails and runtime failure
  handling

### Requirement: SDK Approval Lifecycle

Deepy SHALL implement audit approvals through OpenAI Agents SDK approval
interruptions and resumed run state.

#### Scenario: Tool call pauses for approval

- **WHEN** an SDK run reaches a tool call that requires approval under the active
  audit mode
- **THEN** Deepy SHALL let the SDK pause the run with a tool approval
  interruption
- **AND** Deepy SHALL NOT execute the side-effecting tool before the approval is
  resolved

#### Scenario: User approves an interrupted action

- **WHEN** an SDK run is paused on a tool approval interruption
- **AND** the user approves the action
- **THEN** Deepy SHALL approve the interruption on the SDK run state
- **AND** Deepy SHALL resume the original top-level run from that state

#### Scenario: User rejects an interrupted action

- **WHEN** an SDK run is paused on a tool approval interruption
- **AND** the user rejects the action
- **THEN** Deepy SHALL reject the interruption on the SDK run state
- **AND** Deepy SHALL resume the original top-level run with a model-visible
  rejection result

#### Scenario: Multiple approvals are pending

- **WHEN** an SDK run returns multiple pending approval interruptions
- **THEN** Deepy SHALL present each pending approval for user decision
- **AND** Deepy MAY resume after resolving a subset of interruptions when the
  SDK can preserve unresolved interruptions in the run state

#### Scenario: Subagent approval resumes top-level state

- **WHEN** an SDK run is paused on an approval interruption that originated from
  a subagent tool call
- **AND** the user approves or rejects the action
- **THEN** Deepy SHALL resolve the interruption on the original top-level SDK run
  state
- **AND** Deepy SHALL resume that top-level run without asking the main agent to
  manually replay the subagent command
