## ADDED Requirements

### Requirement: Session Todo Planning

Deepy SHALL provide session-scoped todo planning so complex user requests can be
tracked as structured tasks with visible progress.

#### Scenario: A complex task is planned

- **WHEN** the model creates a todo list for the active user request
- **THEN** Deepy SHALL store the list as the current todo plan for the active
  session
- **AND** each todo item SHALL include a stable `id`, user-facing `content`, and
  `status`
- **AND** supported statuses SHALL include `pending`, `in_progress`, and
  `completed`

#### Scenario: A todo list is updated

- **WHEN** the model updates todo progress
- **THEN** Deepy SHALL replace the current todo plan with the complete updated
  list
- **AND** it SHALL preserve the updated list as the authoritative todo state for
  subsequent rendering, resume, and compaction

#### Scenario: A todo list is cleared

- **WHEN** the model writes an empty todo list
- **THEN** Deepy SHALL clear the current session todo plan
- **AND** the terminal todo board SHALL no longer render stale tasks

### Requirement: Todo Progress Semantics

Deepy SHALL keep todo progress readable and consistent for users.

#### Scenario: One item is in progress

- **WHEN** the current todo plan contains an `in_progress` item
- **THEN** Deepy SHALL treat that item as the current task for board summaries
- **AND** the board SHALL distinguish it from `pending` and `completed` items

#### Scenario: Multiple items are in progress

- **WHEN** the model writes a todo list containing more than one `in_progress`
  item
- **THEN** Deepy SHALL reject the write with a structured tool failure
- **AND** the previous valid todo plan SHALL remain unchanged

#### Scenario: Completed items exist

- **WHEN** the current todo plan contains completed items
- **THEN** Deepy SHALL include completed items in the board unless the board must
  truncate for terminal width or height
- **AND** completed items SHALL be visually distinguishable from pending and
  in-progress items
