## ADDED Requirements

### Requirement: Subagent Configuration Locations

Deepy SHALL store and discover custom subagent definitions under Deepy-owned
configuration directories.

#### Scenario: Project subagent directory exists

- **WHEN** the current project contains `.deepy/subagents`
- **THEN** Deepy SHALL discover valid Markdown subagent definitions in that
  directory
- **AND** it SHALL treat them as project-scoped subagents

#### Scenario: User subagent directory exists

- **WHEN** the user home contains `~/.deepy/subagents`
- **THEN** Deepy SHALL discover valid Markdown subagent definitions in that
  directory
- **AND** it SHALL treat them as user-scoped subagents

#### Scenario: Agent Skills directory exists

- **WHEN** the current project or user home contains `.agents/skills`
- **THEN** Deepy SHALL continue treating that directory as Agent Skills storage
- **AND** it SHALL NOT load files from `.agents/skills` as subagent definitions

### Requirement: Subagent Policy Configuration

Deepy SHALL allow project policy extensions for constrained subagent command
execution.

#### Scenario: Project test-shell policy extends allowlist

- **WHEN** project configuration declares additional `test_shell` allowed command
  patterns
- **THEN** Deepy SHALL consider those patterns during `test_shell` policy
  classification
- **AND** it SHALL still apply global deny rules for destructive and publishing
  commands

#### Scenario: Project test-shell policy requires approval

- **WHEN** project configuration declares additional `test_shell`
  approval-required command patterns
- **THEN** Deepy SHALL classify matching commands as approval-required
- **AND** it SHALL require user approval before execution

#### Scenario: Subagent policy is invalid

- **WHEN** project subagent policy contains invalid command patterns or invalid
  values
- **THEN** Deepy SHALL ignore the invalid policy entries with diagnostics
- **AND** it SHALL continue using built-in safe defaults
