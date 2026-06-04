## MODIFIED Requirements

### Requirement: Bottom Context Status Accuracy

Deepy's bottom toolbar SHALL show Cline-style Context Window usage without a separate compaction pressure token segment.

#### Scenario: Latest request usage is known

- **WHEN** a model request completes with usable token usage
- **THEN** the bottom toolbar SHALL show Context Window usage based on the latest request context occupancy
- **AND** it SHALL show the configured context window as the total
- **AND** it SHALL show the percentage as latest request context occupancy divided by the configured context window
- **AND** it SHALL NOT show a separate `compact` token pressure segment

#### Scenario: Latest turn is short

- **WHEN** a session has existing context and the user sends a short follow-up prompt
- **THEN** the bottom toolbar Context Window usage SHALL reflect the latest request occupancy even when it is lower than the previous request
- **AND** it SHALL NOT show the previous effective session pressure as a second compact value

#### Scenario: Context state is near compaction threshold

- **WHEN** latest request Context Window used tokens are at or above the configured compact threshold
- **THEN** the bottom toolbar SHALL append a concise `compact next` hint to the Context Window segment
- **AND** it SHALL NOT show a separate compaction pressure token count

#### Scenario: Explicit compaction reduces context

- **WHEN** manual or automatic compaction rewrites the active session
- **THEN** Context Window usage SHALL update to the compacted replacement history checkpoint
- **AND** the bottom toolbar SHALL NOT show a separate compacted-history pressure value
- **AND** the compaction success message SHALL use the pre-compaction Context Window used value as its before token count when available

## ADDED Requirements

### Requirement: Token Usage Display Semantics

Deepy's terminal UI SHALL present Token Usage as cumulative API token consumption rather than as context window occupancy.

#### Scenario: Per-turn usage footer is shown

- **WHEN** a model turn completes with usage data
- **THEN** the usage footer SHALL label the displayed values as Token Usage
- **AND** it SHALL include input, output, cache, reasoning, request count, and total fields when known
- **AND** it SHALL NOT imply that the cumulative total is the current Context Window used value

#### Scenario: Session usage is summarized

- **WHEN** Deepy displays accumulated session usage
- **THEN** it SHALL aggregate usage across recorded model requests
- **AND** it SHALL keep the accumulated Token Usage separate from latest request Context Window usage

### Requirement: Context Window Display Semantics

Deepy's terminal UI SHALL present Context Window as latest request occupancy of the configured context window.

#### Scenario: Context window values are shown

- **WHEN** latest request context usage is known
- **THEN** Deepy SHALL show used tokens, total configured context window tokens, remaining tokens, and percentage
- **AND** the used tokens SHALL be derived from latest request context occupancy

#### Scenario: Context window data is unavailable

- **WHEN** latest request context usage is unavailable
- **THEN** Deepy SHALL show the Context Window value as unknown or estimated
- **AND** it SHALL NOT reuse accumulated Token Usage as a fallback Context Window used value
