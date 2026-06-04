## ADDED Requirements

### Requirement: Textual Sessions Survive Storage Replacement
The experimental Textual TUI SHALL preserve user-facing session behavior while
the underlying active session store changes.

#### Scenario: User resumes a TUI session
- **WHEN** a user selects a session from `/resume` or the sessions surface
- **THEN** the TUI SHALL list and restore sessions from the active transactional
  session store
- **AND** subsequent prompts SHALL continue the selected session id

#### Scenario: TUI restores transcript tail
- **WHEN** the TUI restores visible transcript history for a selected session
- **THEN** it SHALL read the requested recent ordered session items from the
  active transactional session store
- **AND** it SHALL render user, assistant, reasoning, tool call, and tool output
  items using the same conventions as live output

#### Scenario: TUI compacts active session
- **WHEN** a user invokes `/compact` in the experimental TUI with an active
  session
- **THEN** Deepy SHALL run durable session compaction against the active
  transactional session store
- **AND** the active session id SHALL remain usable after compaction succeeds

#### Scenario: TUI local command records transcript
- **WHEN** a TUI local command-mode command completes
- **THEN** Deepy SHALL persist the synthetic shell transcript records in the
  active transactional session store
- **AND** later TUI resume and model replay SHALL see the stored local command
  transcript
