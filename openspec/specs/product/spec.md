# Deepy Product Baseline Specification

## Purpose

Deepy is a Python terminal coding agent for DeepSeek's OpenAI-compatible models. It
keeps coding work in one terminal session: read project context, ask questions,
modify files, run commands, search or fetch web content, and resume history later.

This baseline consolidates the completed requirements from `spec/plan-1.md` and
`spec/plan-2.md`.
## Requirements
### Requirement: Python CLI Package

Deepy SHALL be distributed as the `deepy-cli` Python package while exposing the
terminal command `deepy`.

#### Scenario: User installs from PyPI

- **WHEN** a user installs `deepy-cli` with `uv tool install deepy-cli`
- **THEN** the installed console command SHALL be `deepy`

#### Scenario: User asks for version

- **WHEN** a user runs `deepy --version`
- **THEN** Deepy SHALL print the current package version

### Requirement: Project-Centered Terminal Agent

Deepy SHALL use the current working directory as the active project root unless a
command explicitly provides another root.

#### Scenario: User starts Deepy in a project

- **WHEN** a user runs `deepy` inside a project directory
- **THEN** Deepy SHALL start an interactive terminal agent for that project
- **AND** Deepy SHALL show the active model, reasoning settings, version, and CWD

### Requirement: Local-First State

Deepy SHALL keep user configuration and project sessions on the local filesystem.

#### Scenario: Session state is created

- **WHEN** a user starts or resumes a project conversation
- **THEN** Deepy SHALL read and write session state under the user's local
  `~/.deepy` directory

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

### Requirement: Textual Primary UI Migration Stage
Deepy SHALL support a staged migration toward a Textual-primary terminal UI
without switching the default interactive entrypoint in this change.

#### Scenario: User runs default command during migration
- **WHEN** a user runs `deepy`
- **THEN** Deepy SHALL continue to launch the current stable interactive UI
- **AND** it SHALL NOT require users to opt in to Textual behavior

#### Scenario: User runs Textual command during migration
- **WHEN** a user runs `deepy tui`
- **THEN** Deepy SHALL launch the redesigned Textual TUI candidate
- **AND** the command SHALL remain the place to validate Textual-first UX before
  any future default switch

#### Scenario: Future default switch is proposed
- **WHEN** a later change proposes making Textual the default interactive UI
- **THEN** that change SHALL define its own OpenSpec proposal, migration plan,
  compatibility behavior, and stable UI removal or deprecation policy

