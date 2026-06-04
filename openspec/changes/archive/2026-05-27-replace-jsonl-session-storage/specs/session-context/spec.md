## ADDED Requirements

### Requirement: Transactional Local Session Store
Deepy SHALL store active project sessions in a transactional local session store
that keeps session metadata and ordered replay items together.

#### Scenario: A session item is appended
- **WHEN** Deepy writes a new session item
- **THEN** it SHALL store the replayable OpenAI Agents SDK item as the canonical
  item payload
- **AND** it SHALL update the session metadata required for listing, resume,
  context accounting, and status in the same transaction

#### Scenario: A session is replayed
- **WHEN** Deepy replays a session
- **THEN** it SHALL read model replay items from the canonical stored SDK item
  payloads ordered by their session sequence
- **AND** it SHALL NOT rely on display-only history records or historical JSONL
  wrapper fields

#### Scenario: Latest session items are restored
- **WHEN** Deepy restores only the latest visible history for resume or TUI
  rendering
- **THEN** it SHALL read only the requested tail of ordered session items when a
  limit is provided
- **AND** it SHALL preserve the same replay sanitization behavior used for full
  session replay

#### Scenario: Historical JSONL files exist
- **WHEN** a project directory contains old JSONL session files or
  `sessions-index.json`
- **THEN** Deepy SHALL NOT load those files into the active session list
- **AND** it SHALL NOT use them as fallback metadata for replay, resume, context
  accounting, todo state, usage, cost, or process cleanup

### Requirement: Storage-Neutral Session API
Deepy SHALL expose session operations through storage-neutral session APIs rather
than JSONL-specific names or contracts.

#### Scenario: Internal caller opens a session
- **WHEN** runner, compaction, UI, TUI, status, local command, or input
  suggestion code opens a Deepy session
- **THEN** it SHALL use a storage-neutral session abstraction
- **AND** the abstraction SHALL satisfy the OpenAI Agents SDK session protocol
  used by model runs

#### Scenario: Session entries are listed
- **WHEN** Deepy lists project sessions
- **THEN** it SHALL return session entries from the transactional store
- **AND** each entry SHALL include the metadata required by existing session
  pickers, status reports, process cleanup, usage display, and cost summaries

## MODIFIED Requirements

### Requirement: Session Commands
Deepy SHALL keep the user-facing session commands available.

#### Scenario: User manages sessions
- **WHEN** a user runs `/resume`, `deepy sessions list`, or `deepy sessions show`
- **THEN** Deepy SHALL list, select, and display session history from the
  transactional local session store

### Requirement: Compaction Recoverability
Deepy SHALL preserve the pre-compaction session history before replacing the
active session.

#### Scenario: Compaction succeeds
- **WHEN** Deepy successfully generates a compaction summary and replacement
  history
- **THEN** it SHALL archive or snapshot the original active session history
  before making the replacement history active
- **AND** it SHALL make the active replacement and updated session metadata
  visible atomically

#### Scenario: Summary generation fails
- **WHEN** the compaction model call fails
- **THEN** Deepy SHALL leave the original active session history unchanged
- **AND** it SHALL report the compaction failure to the caller

#### Scenario: Replacement write fails
- **WHEN** Deepy cannot persist the replacement history or its metadata
- **THEN** it SHALL roll back to the original active session history when
  possible
- **AND** it SHALL NOT leave the active session in a partially compacted state

## REMOVED Requirements

### Requirement: Python JSONL Session Format
**Reason**: The active session store is moving to a transactional local database
so replay items and metadata can be updated atomically without a separate JSONL
file and index file.

**Migration**: Existing JSONL sessions are intentionally not migrated. New
sessions are created in the transactional local session store.

#### Scenario: A session item is appended
- **WHEN** Deepy writes a new session item
- **THEN** the JSONL record format is no longer used as the active persistence
  contract

#### Scenario: A session is replayed
- **WHEN** Deepy replays a session
- **THEN** historical JSONL wrapper fields are no longer read as the active
  persistence contract
