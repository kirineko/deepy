## ADDED Requirements

### Requirement: Cache-First Session Context
Deepy SHALL model model-visible session context as a stable prefix plus an
append-only session log plus volatile scratch state.

#### Scenario: Normal turn appends context
- **WHEN** a user prompt, assistant response, reasoning content, tool call, or
  tool result is recorded during a normal model turn
- **THEN** Deepy SHALL append the resulting session item after existing active
  items
- **AND** it SHALL NOT rewrite earlier active items as part of the normal turn

#### Scenario: Volatile state changes
- **WHEN** Deepy updates transient runtime state such as live progress, UI-only
  status, temporary planning notes, or diagnostics
- **THEN** it SHALL keep that state outside the replayed model-visible session
  log unless a later step explicitly distills it into persisted session content

#### Scenario: Session resumes
- **WHEN** Deepy resumes a saved session
- **THEN** it SHALL restore the append-only log and cache metadata
- **AND** it SHALL compare the saved cache-prefix fingerprint with the current
  prefix snapshot before the next model request

### Requirement: Explicit Cache Break Recording
Deepy SHALL record cache-breaking context events instead of silently changing
the effective model-visible prefix or log.

#### Scenario: Active history is rewritten
- **WHEN** Deepy compacts, archives and replaces, retries by rolling back,
  recovers from an interrupt by removing active items, or otherwise rewrites
  existing active session items
- **THEN** it SHALL increment the cache context generation
- **AND** it SHALL persist a concise cache break reason with the session

#### Scenario: Prefix source changes
- **WHEN** the active model id, reasoning settings, system prompt stable blocks,
  loaded skill/rule blocks, runtime context boundary, built-in tool schema, or
  MCP tool schema set changes
- **THEN** Deepy SHALL increment the prefix generation before the next model
  request
- **AND** it SHALL persist a cache break reason naming the changed source

#### Scenario: New session starts
- **WHEN** Deepy starts a new session
- **THEN** it SHALL initialize cache metadata for a new prefix generation
- **AND** it SHALL NOT carry cache hit aggregates or cache break reasons from
  the previous session

### Requirement: Cache Usage Aggregation
Deepy SHALL persist cache usage statistics for each session from normalized
provider usage events.

#### Scenario: Usage event includes cache tokens
- **WHEN** a model turn reports `prompt_cache_hit_tokens` and
  `prompt_cache_miss_tokens`
- **THEN** Deepy SHALL persist the per-turn cache hit and miss tokens
- **AND** it SHALL update session-level cache hit and miss aggregates
- **AND** it SHALL compute a session cache hit ratio when the denominator is
  non-zero

#### Scenario: Usage event has no cache token data
- **WHEN** a provider usage event does not include cache hit or miss tokens
- **THEN** Deepy SHALL preserve the model turn usage
- **AND** it SHALL mark cache usage for that turn as unknown rather than zero

### Requirement: Cache-Aligned Context Folding
Deepy SHALL fold or compact context in a way that preserves cache reuse where
possible and records the active-history rewrite where unavoidable.

#### Scenario: Fold request is built
- **WHEN** Deepy builds a summary or fold request for a long session
- **THEN** it SHALL reuse the current stable prefix snapshot where the provider
  boundary permits it
- **AND** it SHALL preserve source conversation content order in the summary
  request
- **AND** it SHALL place the summarization instruction after the source content

#### Scenario: Fold result replaces active history
- **WHEN** Deepy replaces active history with a compacted summary and tail
- **THEN** it SHALL persist the replacement
- **AND** it SHALL record that compaction caused a cache break
- **AND** subsequent status surfaces SHALL be able to show the break reason
