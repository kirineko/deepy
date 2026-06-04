## ADDED Requirements

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
