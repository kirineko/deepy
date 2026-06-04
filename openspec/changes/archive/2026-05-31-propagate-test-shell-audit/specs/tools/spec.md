## MODIFIED Requirements

### Requirement: Constrained Test Shell

Deepy SHALL provide a constrained command execution tool for verification-focused
subagents.

#### Scenario: Test shell command is allowed

- **WHEN** `test_shell` receives a command classified as low-risk development
  verification
- **THEN** Deepy SHALL execute the command with a bounded timeout from the
  project root
- **AND** it SHALL capture stdout, stderr, exit code, command, cwd, elapsed time,
  and truncation metadata
- **AND** it SHALL return a structured result to the calling subagent

#### Scenario: Test shell command requires approval

- **WHEN** `test_shell` receives a useful but medium-risk command such as
  dependency installation, service startup, Docker Compose startup, Rust
  `cargo run`, or local database access that may affect local runtime state
- **THEN** Deepy SHALL NOT execute the command immediately unless the active
  audit policy has approved or auto-approved that command
- **AND** it SHALL surface the command through SDK audit approval when an audit
  policy is active and the audit mode requires command approval
- **AND** it SHALL return a structured `approval_required` result with the
  command, risk classification, and approval reason when no audit approval path
  is active

#### Scenario: Test shell command is denied

- **WHEN** `test_shell` receives a destructive, publishing, source-mutating, or
  unsupported command
- **THEN** Deepy SHALL refuse the command
- **AND** it SHALL return a structured denial reason
- **AND** it SHALL NOT execute any portion of the command

#### Scenario: Shell composition is requested

- **WHEN** `test_shell` receives shell composition syntax such as command
  separators, pipes, redirection, command substitution, heredocs, or background
  operators
- **THEN** Deepy SHALL reject or require explicit approval for the command
  according to policy
- **AND** it SHALL NOT run the command through an unrestricted raw shell by
  default

#### Scenario: Common verification tools are requested

- **WHEN** `test_shell` receives common verification commands for Python, uv,
  pip, Node.js package managers, Java Maven or Gradle, Spring Boot, Rust, Go,
  frontend build/test/lint/typecheck tools, curl, ping, mysql, Docker Compose,
  head, or tail
- **THEN** Deepy SHALL classify the command using a documented allow/approval/
  deny policy
- **AND** the policy SHALL support ordinary test and diagnostic workflows without
  granting raw arbitrary shell access

### Requirement: Test Shell Approval Escalation

Deepy SHALL route test-shell approval needs through the main user interaction
flow.

#### Scenario: Subagent needs command approval

- **WHEN** `test_shell` receives a command classified as `approval_required`
  inside a subagent run
- **THEN** Deepy SHALL surface the command and reason through the outer SDK audit
  approval flow when an audit policy is active and the audit mode requires
  command approval
- **AND** Deepy SHALL wait for the user's audit decision before executing the
  command

#### Scenario: User approves command

- **WHEN** the user approves a `test_shell` command through the outer audit flow
- **THEN** Deepy SHALL execute the approved command through the constrained
  `test_shell` path
- **AND** it SHALL NOT grant the subagent raw unrestricted shell access

#### Scenario: Audit mode auto-approves command

- **WHEN** `test_shell` receives a command classified as `approval_required`
- **AND** the active audit mode auto-approves command execution
- **THEN** Deepy SHALL execute the command through the constrained `test_shell`
  path without a separate in-band token retry
- **AND** hard-denied `test_shell` policy decisions SHALL remain denied

#### Scenario: User rejects command

- **WHEN** the user rejects a `test_shell` command approval request
- **THEN** Deepy SHALL NOT execute the command
- **AND** the subagent or main agent SHALL report the verification limitation
  clearly

#### Scenario: No audit approval path is active

- **WHEN** `test_shell` receives a command classified as `approval_required`
- **AND** Deepy has no active SDK audit policy for that invocation
- **THEN** Deepy MAY return a structured `approval_required` result with an
  approval token
- **AND** a retry using that token SHALL execute only the same command through
  the constrained `test_shell` path

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

#### Scenario: Test shell medium-risk command is approval-gated

- **WHEN** the active audit mode requires command approval
- **AND** a subagent invokes `test_shell` with a command classified as
  `approval_required`
- **THEN** Deepy SHALL pause the SDK run for approval before executing the
  constrained command
- **AND** the approval SHALL apply only to that `test_shell` command invocation

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
