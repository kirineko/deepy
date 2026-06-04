## MODIFIED Requirements

### Requirement: Bottom Context Status Accuracy

Deepy's interactive status footer SHALL show Cline-style Context Window usage without a separate compaction pressure token segment.

#### Scenario: Latest request usage is known

- **WHEN** a model request completes with usable token usage
- **THEN** the footer SHALL show Context Window usage based on the latest request context occupancy
- **AND** it SHALL use a compact `ctx` label for that segment
- **AND** it SHALL show the configured context window as the total
- **AND** it SHALL show the percentage as latest request context occupancy divided by the configured context window
- **AND** it SHALL NOT show a separate `compact` token pressure segment
- **AND** it SHALL NOT use the redundant label `ctx win`

#### Scenario: Latest turn is short

- **WHEN** a session has existing context and the user sends a short follow-up prompt
- **THEN** the footer Context Window usage SHALL reflect the latest request occupancy even when it is lower than the previous request
- **AND** it SHALL NOT show the previous effective session pressure as a second compact value

#### Scenario: Esc-only prompt rollback occurs

- **WHEN** a submitted prompt is interrupted with Esc before the turn persists assistant or tool output
- **AND** the previous session state has known latest request Context Window usage
- **THEN** the prompt footer SHALL continue to show the previous latest request Context Window usage
- **AND** it SHALL NOT show internal active-token estimates as Context Window used tokens

#### Scenario: Context state is near compaction threshold

- **WHEN** latest request Context Window used tokens are at or above the configured compact threshold
- **THEN** the footer SHALL append a concise `compact next` hint to the `ctx` segment
- **AND** it SHALL NOT show a separate compaction pressure token count

#### Scenario: Explicit compaction reduces context

- **WHEN** manual or automatic compaction rewrites the active session
- **THEN** Context Window usage SHALL update to the compacted replacement history checkpoint
- **AND** the footer SHALL NOT show a separate compacted-history pressure value
- **AND** the compaction success message SHALL use the pre-compaction Context Window used value as its before token count when available
