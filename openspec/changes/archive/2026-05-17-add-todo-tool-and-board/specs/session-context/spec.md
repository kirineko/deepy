## ADDED Requirements

### Requirement: Todo State Persistence

Deepy SHALL preserve the latest valid todo plan with the active session.

#### Scenario: Todo plan is updated

- **WHEN** `todo_write` successfully updates the active todo plan
- **THEN** Deepy SHALL persist the latest todo state with the active session
- **AND** the persisted state SHALL be sufficient to restore the board without
  reparsing assistant prose

#### Scenario: Session is resumed

- **WHEN** a user resumes a session with a persisted todo plan
- **THEN** Deepy SHALL restore the latest valid todo state
- **AND** the terminal UI SHALL be able to render the restored todo board or
  compact summary

#### Scenario: Session is compacted

- **WHEN** manual or automatic compaction rewrites a session that has an active
  todo plan
- **THEN** Deepy SHALL preserve the latest todo state across the compaction
- **AND** the compaction prompt SHALL include enough todo context for the model
  to continue or reconcile the plan

#### Scenario: Invalid todo update occurs

- **WHEN** a `todo_write` call fails validation
- **THEN** Deepy SHALL NOT persist the invalid todo list
- **AND** it SHALL keep the latest previous valid todo state for resume and
  compaction
