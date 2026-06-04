## ADDED Requirements

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
