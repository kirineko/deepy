## ADDED Requirements

### Requirement: Built-In Tool Audit Enforcement

Deepy SHALL apply the active system audit mode to built-in tools that can create
external side effects.

#### Scenario: Managed text write is approval-gated

- **WHEN** the active audit mode requires text write approval
- **AND** the model invokes `Write` or `Update`
- **THEN** Deepy SHALL pause the SDK run for approval before invoking the
  managed text mutation
- **AND** the mutation SHALL NOT be committed unless the user approves the
  interrupted tool call

#### Scenario: Shell command is approval-gated

- **WHEN** the active audit mode requires command approval
- **AND** the model invokes `shell`
- **THEN** Deepy SHALL pause the SDK run for approval before starting the shell
  command
- **AND** this SHALL apply to both foreground commands and commands requested
  with `run_in_background`

#### Scenario: Background task termination is approval-gated

- **WHEN** the active audit mode requires command approval
- **AND** the model invokes `task_stop`
- **THEN** Deepy SHALL pause the SDK run for approval before requesting task
  termination

#### Scenario: Read-only built-in tools remain ungated

- **WHEN** the model invokes `Search`, `Read`, `WebSearch`, `WebFetch`,
  `task_list`, or `task_output`
- **THEN** Deepy SHALL NOT require audit approval solely because of the active
  audit mode

#### Scenario: Session planning remains ungated

- **WHEN** the model invokes `todo_write`
- **THEN** Deepy SHALL NOT treat the session todo update as a managed text write
  for audit approval purposes

### Requirement: Approval Preview Metadata

Deepy SHALL provide enough information for approval UI surfaces to summarize
pending built-in tool approvals before execution.

#### Scenario: Text write approval is displayed

- **WHEN** a pending approval is for `Write` or `Update`
- **THEN** Deepy SHALL show the tool name and target path or paths
- **AND** Deepy SHALL show a concise diff or content-change preview when it can
  be computed before committing the mutation

#### Scenario: Shell approval is displayed

- **WHEN** a pending approval is for `shell`
- **THEN** Deepy SHALL show the exact command string
- **AND** it SHALL show the current working directory for the command

#### Scenario: Task stop approval is displayed

- **WHEN** a pending approval is for `task_stop`
- **THEN** Deepy SHALL show the target background task id
