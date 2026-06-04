## ADDED Requirements

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
  dependency installation, service startup, Docker Compose startup, or local
  database access that may affect local runtime state
- **THEN** Deepy SHALL NOT execute the command immediately
- **AND** it SHALL return a structured `approval_required` result with the
  command, risk classification, and approval reason

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

### Requirement: Subagent Tool Exposure

Deepy SHALL expose only policy-approved tools to subagents.

#### Scenario: Explore tools are exposed

- **WHEN** Deepy constructs the built-in `explore` subagent
- **THEN** it SHALL expose local search and file-read tools
- **AND** it MAY expose web fetch/search and search-class MCP tools
- **AND** it SHALL NOT expose source mutation tools by default

#### Scenario: Reviewer tools are exposed

- **WHEN** Deepy constructs the built-in `reviewer` subagent
- **THEN** it SHALL expose local search and file-read tools
- **AND** it SHALL NOT expose source mutation tools by default
- **AND** it SHALL NOT expose `test_shell` by default

#### Scenario: Tester tools are exposed

- **WHEN** Deepy constructs the built-in `tester` subagent
- **THEN** it SHALL expose local search, file-read, and `test_shell`
- **AND** it SHALL NOT expose source mutation tools by default
- **AND** it SHALL NOT expose the raw unrestricted `shell` tool by default

### Requirement: Test Shell Approval Escalation

Deepy SHALL route test-shell approval needs through the main user interaction
flow.

#### Scenario: Subagent needs command approval

- **WHEN** `test_shell` returns `approval_required` inside a subagent run
- **THEN** the main Deepy agent SHALL surface the command and reason to the user
  through `AskUserQuestion`
- **AND** Deepy SHALL wait for the user's decision before executing the command

#### Scenario: User approves command

- **WHEN** the user approves a `test_shell` command
- **THEN** Deepy SHALL allow the approved command to be retried through the
  constrained `test_shell` path
- **AND** it SHALL NOT grant the subagent raw unrestricted shell access

#### Scenario: User rejects command

- **WHEN** the user rejects a `test_shell` command approval request
- **THEN** Deepy SHALL NOT execute the command
- **AND** the subagent or main agent SHALL report the verification limitation
  clearly
