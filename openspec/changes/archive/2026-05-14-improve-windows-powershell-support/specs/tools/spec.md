## ADDED Requirements

### Requirement: Cross-Platform Shell Execution

Deepy SHALL execute model-requested shell commands using a wrapper compatible
with the detected command dialect while preserving the existing model-facing
shell tool contract.

#### Scenario: POSIX shell command is executed

- **WHEN** the active command dialect is `posix`
- **AND** the model invokes the shell execution tool
- **THEN** Deepy SHALL execute the command through a POSIX-compatible shell
- **AND** it SHALL preserve cwd changes between shell tool calls
- **AND** it SHALL return structured metadata including cwd, exit code, process
  id, shell path, shell kind, command dialect, and path style

#### Scenario: PowerShell command is executed

- **WHEN** the active command dialect is `powershell`
- **AND** the model invokes the shell execution tool
- **THEN** Deepy SHALL execute the command through PowerShell or PowerShell Core
- **AND** it SHALL preserve cwd changes between shell tool calls
- **AND** it SHALL capture a normalized integer exit code
- **AND** it SHALL return structured metadata including cwd, exit code, process
  id, shell path, shell kind, command dialect, and path style

#### Scenario: Shell command times out

- **WHEN** a shell command exceeds its timeout
- **THEN** Deepy SHALL terminate the running process
- **AND** it SHALL return a structured tool failure
- **AND** the failure metadata SHALL include cwd, timeout, process id, shell path,
  shell kind, command dialect, interrupted status, and output truncation status

### Requirement: Shell Tool Guidance

Deepy SHALL expose the model-facing shell execution tool as `shell` and describe
it as current-environment shell execution rather than bash-only execution.

#### Scenario: Tool documentation is loaded

- **WHEN** Deepy builds tool documentation for the model
- **THEN** the `shell` tool documentation SHALL state that commands must match the
  detected runtime shell and command dialect
- **AND** it SHALL mention PowerShell behavior for Windows PowerShell

#### Scenario: Function tools are registered

- **WHEN** Deepy registers function tools for the model
- **THEN** the registered shell execution tool SHALL be named `shell`
- **AND** the shell execution tool description SHALL avoid implying that every
  command runs in bash
