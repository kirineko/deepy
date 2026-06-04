## MODIFIED Requirements

### Requirement: Context And Compact Display

Deepy SHALL show Context Window occupancy as the only user-facing context pressure value, and automatic compaction timing SHALL use latest request Context Window usage when available.

#### Scenario: A model turn completes

- **WHEN** Deepy receives usage for one or more model requests in a user turn
- **THEN** it SHALL display per-turn Token Usage details after the response
- **AND** it SHALL update the Context Window display with latest request used tokens, total context window, remaining tokens, and percentage
- **AND** it SHALL NOT show a separate `compact` or compaction pressure token segment
- **AND** it SHALL use latest request Context Window usage to determine whether the next turn should auto compact when that usage is available

#### Scenario: A session is compacted

- **WHEN** manual or automatic compaction rewrites a session
- **THEN** Deepy SHALL update the persisted session history to the compacted summary plus preserved recent context
- **AND** this explicit rewrite SHALL reset the persisted Context Window checkpoint to the compacted session estimate
- **AND** the next Context Window display and auto-compact decision SHALL use the reset checkpoint until a newer provider usage record is available
- **AND** any user-facing compaction summary SHALL report its before value from the same Context Window checkpoint shown in the statusline when that checkpoint is available

#### Scenario: Interrupted prompt rollback preserves latest context checkpoint

- **WHEN** an Esc interrupt rolls back only the newly persisted user prompt
- **AND** the active session already has a latest request Context Window checkpoint
- **THEN** Deepy SHALL preserve that latest request Context Window checkpoint
- **AND** it SHALL NOT replace the checkpoint with internal active-token estimates
- **AND** it MAY update active-token and pending-token metadata used for compaction decisions

#### Scenario: Pending context exists

- **WHEN** session messages have been appended after the latest precise usage checkpoint
- **THEN** Deepy SHALL NOT show pending estimated tokens as a separate statusline pressure value
- **AND** it SHALL NOT add pending estimated tokens to the latest request Context Window used value

#### Scenario: Provider usage is unknown

- **WHEN** the latest model request does not provide usable token usage
- **THEN** Deepy SHALL render Context Window usage as unknown or estimated
- **AND** it SHALL NOT substitute cumulative Token Usage as Context Window usage
- **AND** automatic compaction MAY fall back to local history estimates to avoid sending obviously oversized requests

#### Scenario: Latest request reaches compaction threshold

- **WHEN** latest request Context Window used tokens are greater than or equal to the configured context window multiplied by the compact trigger ratio
- **THEN** Deepy SHALL automatically compact before the next model request
- **AND** the same condition SHALL drive any `compact next` statusline hint

#### Scenario: A new session is started

- **WHEN** the user starts a new session
- **THEN** Deepy SHALL clear the active session Context Window checkpoint from the statusline
- **AND** it SHALL NOT carry the previous session's Context Window used value or `compact next` hint into the new session
