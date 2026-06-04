## ADDED Requirements

### Requirement: Cache Health Status Display
The default terminal UI SHALL expose DeepSeek cache health when cache usage data
is available.

#### Scenario: Usage includes cache tokens
- **WHEN** a model turn completes with cache hit and miss token data
- **THEN** the terminal UI SHALL be able to show fresh input tokens, cached
  input tokens, and cache hit ratio
- **AND** it SHALL use the normalized usage values persisted for the session

#### Scenario: Cache usage is unknown
- **WHEN** the active provider or model turn does not report cache hit and miss
  token data
- **THEN** the terminal UI SHALL show cache health as unknown or omit the cache
  metric
- **AND** it SHALL NOT imply a zero percent cache hit ratio

#### Scenario: Status command is rendered
- **WHEN** the user opens `/status`
- **THEN** Deepy SHALL include the active prefix generation, session cache hit
  ratio when known, and latest cache-break reason when present

### Requirement: Cache Break Visibility
The default terminal UI SHALL surface cache-breaking context changes without
interrupting the user's workflow.

#### Scenario: Cache break occurs during a turn
- **WHEN** Deepy records a cache break from compaction, retry recovery, interrupt
  cleanup, prefix change, or tool-set change
- **THEN** the terminal UI SHALL make the reason available in status or usage
  surfaces
- **AND** it SHALL keep the reason concise enough for terminal display

#### Scenario: Cache metadata contains secrets
- **WHEN** cache health or cache break information is rendered
- **THEN** the terminal UI SHALL NOT print API keys, authorization headers, or
  full provider payloads
