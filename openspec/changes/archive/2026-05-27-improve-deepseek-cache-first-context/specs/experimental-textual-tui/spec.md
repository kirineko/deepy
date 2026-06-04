## ADDED Requirements

### Requirement: Textual Cache Health Display
The experimental Textual TUI SHALL expose cache health using the same normalized
session metadata as the default terminal UI.

#### Scenario: TUI session has cache usage data
- **WHEN** the active Textual TUI session has cache hit and miss token data
- **THEN** the TUI SHALL show cache hit ratio and cached/fresh input token
  information in an appropriate status, footer, detail, or session view
- **AND** it SHALL update that display after model turns complete

#### Scenario: TUI session has unknown cache usage
- **WHEN** the active provider or model turn does not report cache hit and miss
  token data
- **THEN** the TUI SHALL show cache health as unknown or omit the cache metric
- **AND** it SHALL NOT imply a zero percent cache hit ratio

### Requirement: Textual Cache Break Visibility
The experimental Textual TUI SHALL make cache-breaking context changes visible
without depending on provider-specific raw events.

#### Scenario: Cache break is recorded
- **WHEN** Deepy records a cache break from compaction, retry recovery, interrupt
  cleanup, prefix change, or tool-set change
- **THEN** the Textual TUI SHALL make the latest cache-break reason available in
  status, footer, detail, or session views
- **AND** it SHALL consume the normalized Deepy session metadata instead of raw
  provider event objects

#### Scenario: Cache metadata is rendered
- **WHEN** the Textual TUI renders cache health or cache-break information
- **THEN** it SHALL NOT print API keys, authorization headers, or full provider
  payloads
