## MODIFIED Requirements

### Requirement: Constrained Test Shell

Deepy SHALL provide a constrained command execution tool for verification-focused
subagents.

#### Scenario: Test shell command requires approval

- **WHEN** `test_shell` receives a useful but medium-risk command such as
  direct Python or Python3 script/code execution, dependency installation,
  service startup, Docker Compose startup, Rust `cargo run`, Go `go run`, Node
  package scripts that run local code, Java Maven or Gradle application startup,
  or local database access that may affect local runtime state
- **THEN** Deepy SHALL NOT execute the command immediately unless the active
  audit policy has approved or auto-approved that command
- **AND** it SHALL surface the command through SDK audit approval when an audit
  policy is active and the audit mode requires command approval
- **AND** it SHALL return a structured `approval_required` result with the
  command, risk classification, and approval reason when no audit approval path
  is active

#### Scenario: Common verification tools are requested

- **WHEN** `test_shell` receives common verification commands for Python, uv,
  pip, Node.js package managers, Java Maven or Gradle, Spring Boot, Rust, Go,
  frontend build/test/lint/typecheck tools, curl, ping, mysql, Docker Compose,
  head, or tail
- **THEN** Deepy SHALL classify the command using a documented allow/approval/
  deny policy
- **AND** direct local-code execution SHALL be classified as medium-risk
  `approval_required` rather than hard-denied solely because the command is an
  application run command
- **AND** the policy SHALL support ordinary test and diagnostic workflows without
  granting raw arbitrary shell access
