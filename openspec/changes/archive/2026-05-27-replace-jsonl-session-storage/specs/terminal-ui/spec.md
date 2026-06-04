## ADDED Requirements

### Requirement: Stable Terminal Sessions Survive Storage Replacement
Deepy's stable terminal UI SHALL preserve user-facing session behavior while the
underlying active session store changes.

#### Scenario: User resumes a stored session
- **WHEN** a user opens `/resume` in the stable terminal UI
- **THEN** Deepy SHALL show sessions from the active transactional session store
  with first prompt, status, time, and history estimate when known
- **AND** selected history SHALL be rendered using the same transcript display
  conventions as live output

#### Scenario: User runs session list command
- **WHEN** a user runs the stable terminal session listing command
- **THEN** Deepy SHALL list sessions from the active transactional session store
- **AND** it SHALL NOT list sessions that exist only as historical JSONL files
  or `sessions-index.json` entries

#### Scenario: User compacts active session
- **WHEN** a user runs `/compact` while an active stable terminal session has
  compactable history
- **THEN** Deepy SHALL run durable session compaction against the active
  transactional session store
- **AND** the active session SHALL remain resumable after compaction succeeds

#### Scenario: Stable terminal command records local transcript
- **WHEN** a stable terminal local command-mode command completes
- **THEN** Deepy SHALL persist the synthetic shell transcript records in the
  active transactional session store
- **AND** later resume and model replay SHALL see the stored local command
  transcript
