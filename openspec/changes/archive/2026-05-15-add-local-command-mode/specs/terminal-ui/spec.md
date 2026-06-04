## ADDED Requirements

### Requirement: Local Command Mode
Deepy's interactive terminal prompt SHALL execute prompts beginning with `!` as
local shell commands without sending that prompt to the model.

#### Scenario: User runs a local command
- **WHEN** a user submits prompt text whose trimmed value starts with `!`
- **AND** the text after `!` contains a non-empty command
- **THEN** Deepy SHALL execute that command locally instead of sending the
  prompt to the model
- **AND** Deepy SHALL render the command result in the terminal

#### Scenario: User submits an empty local command
- **WHEN** a user submits `!` with no command text after it
- **THEN** Deepy SHALL show a concise usage message
- **AND** it SHALL NOT send a model request
- **AND** it SHALL NOT append a command transcript to the session

#### Scenario: Local command uses the detected shell
- **WHEN** Deepy executes a local command-mode command
- **THEN** it SHALL use the current runtime shell dialect for the user's
  platform, including zsh or bash on POSIX-like systems and PowerShell or cmd on
  Windows

#### Scenario: Local command has a terminal environment
- **WHEN** Deepy executes a local command-mode command
- **THEN** it SHALL provide a TTY or PTY-backed execution environment
- **AND** Windows TTY execution SHALL use `pywinpty`

#### Scenario: Local command exits
- **WHEN** a local command completes
- **THEN** Deepy SHALL render captured terminal output
- **AND** it SHALL render whether the command succeeded or the exit code when it
  failed

#### Scenario: Local command is interrupted or times out
- **WHEN** a local command is interrupted or exceeds the configured timeout
- **THEN** Deepy SHALL terminate the command when possible
- **AND** it SHALL render the partial captured output and interrupted status

#### Scenario: Local command attempts to change directory
- **WHEN** a user runs a local command such as `!cd subdir`
- **THEN** that command SHALL NOT change Deepy's active project root
- **AND** it SHALL NOT change the working directory used for future local
  command-mode commands

#### Scenario: User enters normal prompt text
- **WHEN** a user submits prompt text that does not start with `!` after
  trimming
- **THEN** Deepy SHALL keep the existing model prompt behavior

#### Scenario: Local command output is long
- **WHEN** local command output exceeds the terminal display limit
- **THEN** Deepy SHALL bound the displayed output
- **AND** it SHALL indicate that output was truncated
