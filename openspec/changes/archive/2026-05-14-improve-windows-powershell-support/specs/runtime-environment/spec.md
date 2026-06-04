## ADDED Requirements

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
