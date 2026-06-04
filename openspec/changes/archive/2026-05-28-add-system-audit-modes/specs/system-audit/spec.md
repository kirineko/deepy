## ADDED Requirements

### Requirement: Audit Modes

Deepy SHALL provide a system audit mode that controls whether model-requested
side-effecting actions require user approval before execution.

#### Scenario: Normal mode requires approval for side effects

- **WHEN** the active audit mode is `normal`
- **AND** the model requests a managed text write, shell command execution,
  background task termination, or MCP tool call
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
- **AND** the model requests shell command execution or background task
  termination
- **THEN** Deepy SHALL require user approval before executing the requested
  action

#### Scenario: Yolo mode auto-approves side effects

- **WHEN** the active audit mode is `yolo`
- **AND** the model requests a managed text write, shell command execution,
  background task termination, or MCP tool call
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

### Requirement: Audit Guardrail Preservation

Audit mode SHALL NOT disable Deepy's hard safety guardrails.

#### Scenario: Yolo mode encounters hard-denied mutation

- **WHEN** the active audit mode is `yolo`
- **AND** a managed text mutation targets a path outside the project, escapes via
  symlink, targets unsupported content, mutates blocked repository internals, or
  fails stale-write checks
- **THEN** Deepy SHALL reject the mutation
- **AND** it SHALL NOT ask the user to approve bypassing that hard guardrail

#### Scenario: Approval mode encounters runtime failure

- **WHEN** an approved tool call fails due to SDK, MCP, shell, file-system, or
  runtime errors
- **THEN** Deepy SHALL report the failure through the existing tool result or
  terminal error surface
- **AND** the approval decision SHALL NOT be treated as a guarantee of success
