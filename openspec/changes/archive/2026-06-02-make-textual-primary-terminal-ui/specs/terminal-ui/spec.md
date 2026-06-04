## ADDED Requirements

### Requirement: Stable UX Semantics For Textual Redesign
The redesigned Textual TUI SHALL preserve the stable terminal UI's core user
experience semantics where those semantics define everyday Deepy behavior.

#### Scenario: Prompt keyboard semantics are preserved
- **WHEN** a user moves from the stable UI to the redesigned Textual TUI
- **THEN** Enter SHALL submit the prompt
- **AND** Ctrl+J SHALL insert a newline
- **AND** Esc SHALL remain available for interruption or prompt-local escape
  behavior

#### Scenario: Command semantics are preserved
- **WHEN** a user invokes slash commands that are supported by both surfaces
- **THEN** the redesigned Textual TUI SHALL preserve the stable UI's command
  behavior, confirmations, and error semantics unless the change explicitly
  documents a Textual-specific interaction form

#### Scenario: Runtime summary semantics are preserved
- **WHEN** the Textual TUI shows running status, usage, context pressure,
  compact-next state, or exit summaries
- **THEN** the displayed meaning SHALL match the stable UI behavior
- **AND** Textual-specific layout SHALL NOT change the underlying status
  semantics

### Requirement: Stable UI Retirement Preparation
Deepy SHALL treat the redesigned Textual TUI as preparation for a future stable
UI retirement without removing the stable UI in this change.

#### Scenario: New Textual behavior is implemented
- **WHEN** implementation adds redesigned Textual behavior
- **THEN** the behavior SHALL be tested in the Textual surface
- **AND** implementation SHOULD avoid adding duplicate stable/TUI code paths
  unless needed to preserve existing stable UI behavior during the migration

#### Scenario: Future stable UI removal is considered
- **WHEN** maintainers evaluate a later change to make Textual the default and
  remove the stable UI
- **THEN** they SHALL verify Textual input reliability, command coverage,
  transcript rendering, approvals, sessions, skills, status, background tasks,
  documentation, and cross-terminal behavior before removing the stable UI
