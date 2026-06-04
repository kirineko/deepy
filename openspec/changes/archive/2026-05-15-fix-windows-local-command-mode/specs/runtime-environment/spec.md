## ADDED Requirements

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
