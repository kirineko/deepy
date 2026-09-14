## MODIFIED Requirements

### Requirement: Bottom Context Status Accuracy

Deepy's interactive status footer SHALL show Cline-style Context Window usage without a separate compaction pressure token segment.

#### Scenario: Latest request usage is known

- **WHEN** a model request completes with usable token usage matching the current model and active history view
- **THEN** the footer SHALL show Context Window usage based on the latest request context occupancy
- **AND** it SHALL use a compact `ctx` label for that segment
- **AND** it SHALL show the resolved effective model context window as the total
- **AND** it SHALL show the percentage as latest request context occupancy divided by the resolved effective model context window
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

- **WHEN** the complete next-request budget reaches the compact threshold or exhausts the output-and-safety reserve
- **THEN** the footer SHALL append a concise `!` compaction hint to the `ctx` segment
- **AND** it SHALL NOT show a separate compaction pressure token count

#### Scenario: Explicit compaction reduces context

- **WHEN** manual or automatic compaction rewrites the active session
- **THEN** Context Window usage SHALL update to the compacted replacement history checkpoint
- **AND** the footer SHALL NOT show a separate compacted-history pressure value
- **AND** the compaction success message SHALL identify its before value as reported occupancy or a next-request estimate consistent with the footer

### Requirement: Context Window Display Semantics

Deepy's terminal UI SHALL present Context Window as latest request occupancy of the resolved effective model context window.

#### Scenario: Context window values are shown

- **WHEN** latest request context usage is known and applicable to the current model and history view
- **THEN** Deepy SHALL show used tokens, total resolved effective model context window tokens and percentage in the footer using compact K/M units
- **AND** remaining tokens and full source/readiness descriptions SHALL remain available in status/doctor diagnostics
- **AND** the used tokens SHALL be derived from latest request context occupancy

#### Scenario: Context window data is unavailable

- **WHEN** latest request context usage is unavailable
- **THEN** Deepy SHALL show the Context Window value as unknown or estimated
- **AND** it SHALL NOT reuse accumulated Token Usage as a fallback Context Window used value

## ADDED Requirements

### Requirement: Model Switch Context Recovery
Deepy SHALL expose the selected model's effective context and history readiness in Classic UI.

#### Scenario: Model selection changes
- **WHEN** a user switches model at a safe idle boundary
- **THEN** the footer SHALL immediately use the target effective window and mark its occupancy estimated or pending validation
- **AND** it SHALL distinguish conservative or unverified proxy limits with short symbols without adding a second pressure counter
- **AND** `~` before usage SHALL indicate an estimate, `~` after the window a conservative limit, `?` after the window an unverified proxy, and `-` unavailable usage

#### Scenario: Explicit text summary requested
- **WHEN** the user runs /compact --for-model for the currently selected target
- **THEN** Deepy SHALL prepare a budgeted target view and treat this as explicit permission to summarize incompatible image history into text
- **AND** it SHALL identify any source model used and retain the originals

#### Scenario: Preparation is blocked or cancelled
- **WHEN** the target view cannot be prepared or the user cancels preparation
- **THEN** Deepy SHALL preserve the draft and images, show recovery guidance and refrain from sending the target request
