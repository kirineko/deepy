## ADDED Requirements

### Requirement: Experimental TUI Command
Deepy SHALL expose the experimental Textual terminal UI through a dedicated
opt-in CLI command while preserving the existing stable command behavior.

#### Scenario: User runs experimental TUI command
- **WHEN** a user runs `deepy tui`
- **THEN** Deepy SHALL start the experimental Textual terminal UI
- **AND** it SHALL NOT require users to change configuration before trying the
  experimental UI

#### Scenario: User runs default command
- **WHEN** a user runs `deepy` without a subcommand
- **THEN** Deepy SHALL continue to start the stable interactive terminal agent
- **AND** it SHALL NOT start the experimental Textual TUI by default

#### Scenario: User asks for CLI help
- **WHEN** a user runs `deepy --help`
- **THEN** Deepy SHALL list `tui` as an available experimental subcommand
- **AND** the help text SHALL make clear that the command is experimental
