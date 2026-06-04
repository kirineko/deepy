# runtime-environment Specification

## Purpose
TBD - created by archiving change improve-windows-powershell-support. Update Purpose after archive.
## Requirements
### Requirement: Runtime Environment Classification

Deepy SHALL classify the user's runtime environment into explicit fields that
the model can use for command and path selection.

#### Scenario: Windows PowerShell environment is detected

- **WHEN** Deepy starts an agent session on Windows with PowerShell or PowerShell
  Core as the active shell
- **THEN** the runtime environment SHALL identify the OS family as `windows`
- **AND** it SHALL identify the shell kind as `powershell`
- **AND** it SHALL identify the command dialect as `powershell`
- **AND** it SHALL identify the preferred path style as `windows`

#### Scenario: POSIX environment is detected

- **WHEN** Deepy starts an agent session on Linux or macOS with bash or zsh as the
  active shell
- **THEN** the runtime environment SHALL identify the command dialect as `posix`
- **AND** it SHALL identify the preferred path style as `posix`

#### Scenario: Environment is ambiguous

- **WHEN** Deepy cannot confidently classify the active shell
- **THEN** the runtime environment SHALL expose `unknown` for the ambiguous shell
  fields
- **AND** it SHALL still expose the detected OS family when available

### Requirement: Runtime Prompt Guidance

Deepy SHALL include concise runtime environment guidance in the system prompt so
the model chooses commands that match the user's actual operating system and
shell.

#### Scenario: Prompt includes command dialect

- **WHEN** Deepy builds the system prompt for a model turn
- **THEN** the prompt SHALL include the detected OS family, shell kind, command
  dialect, and path style
- **AND** it SHALL instruct the model to prefer commands compatible with that
  command dialect

#### Scenario: Prompt is built for Windows PowerShell

- **WHEN** the runtime environment command dialect is `powershell`
- **THEN** the prompt SHALL guide the model to prefer PowerShell-compatible
  commands and Windows path syntax
- **AND** it SHALL NOT imply that bash, zsh, or POSIX utilities are the default
  execution environment

### Requirement: Runtime Encoding Compatibility Context

Deepy SHALL expose enough runtime context for Windows encoding compatibility decisions without changing existing runtime classification behavior for macOS and Linux.

#### Scenario: Windows PowerShell encoding context is available

- **WHEN** Deepy starts an agent session on Windows with PowerShell or PowerShell Core as the active shell
- **THEN** the runtime environment SHALL continue to identify the OS family as `windows`
- **AND** it SHALL continue to identify the command dialect as `powershell`
- **AND** Windows-specific shell encoding compatibility may be applied only to Windows shell invocations

#### Scenario: POSIX runtime classification remains unchanged

- **WHEN** Deepy starts an agent session on Linux or macOS with bash or zsh as the active shell
- **THEN** the runtime environment SHALL continue to identify the command dialect as `posix`
- **AND** it SHALL NOT imply that Windows code-page compatibility behavior is active

### Requirement: Windows Local Command Execution Boundary
Deepy SHALL treat Windows local command mode as a non-interactive subprocess
execution path rather than as an embedded terminal emulator.

#### Scenario: Windows local command execution is selected
- **WHEN** Deepy detects that local command mode is running on Windows
- **THEN** it SHALL execute local commands without allocating a pseudo-terminal
- **AND** it SHALL capture command output through process pipes
- **AND** it SHALL keep the detected shell kind and command dialect metadata
  available for rendering and session persistence

#### Scenario: Windows local command metadata is reported
- **WHEN** Deepy records metadata for a Windows local command-mode result
- **THEN** the TTY mode metadata SHALL indicate that the command used a
  non-interactive pipe-based execution path
- **AND** the metadata SHALL continue to include shell path, shell kind, command
  dialect, path style, cwd, exit code, duration, timeout, and interruption state
  when available

#### Scenario: POSIX local command execution is unaffected
- **WHEN** Deepy executes local command mode on macOS or Linux
- **THEN** the existing POSIX PTY-backed execution behavior SHALL remain
  available
- **AND** the Windows non-interactive boundary SHALL NOT change POSIX runtime
  classification

