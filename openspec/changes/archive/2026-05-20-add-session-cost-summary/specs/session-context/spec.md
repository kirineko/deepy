## ADDED Requirements

### Requirement: Session Cost Snapshot Metadata
Deepy SHALL persist optional session cost metadata separately from Token Usage
and Context Window accounting.

#### Scenario: Session balance snapshots are recorded
- **WHEN** Deepy records starting and ending DeepSeek balance snapshots for an
  interactive session
- **THEN** it SHALL store the snapshot metadata with the session index entry
- **AND** it SHALL preserve each known currency independently
- **AND** it SHALL store enough information to render starting balance, ending
  balance, computed spend, and unavailable reason when known

#### Scenario: Cost metadata is absent
- **WHEN** Deepy reads an existing session index entry without cost metadata
- **THEN** it SHALL treat session cost as unknown
- **AND** it SHALL keep existing session usage, input suggestion usage, active
  token estimates, and Context Window checkpoints intact

#### Scenario: Session cost is computed
- **WHEN** a session has valid starting and ending balances for the same
  currency
- **THEN** Deepy SHALL compute spend from the positive decrease in
  `total_balance`
- **AND** it SHALL NOT use cumulative Token Usage totals as money values
- **AND** it SHALL NOT update Context Window usage or compaction checkpoints
  from cost metadata

#### Scenario: Balance delta is not reliable
- **WHEN** either balance snapshot is unavailable, currencies do not match, or
  a balance increases during the session
- **THEN** Deepy SHALL mark session cost as unavailable or not measurable for
  that currency
- **AND** it SHALL keep local usage metadata visible to callers
