## ADDED Requirements

### Requirement: Subagent Session Recording

Deepy SHALL record subagent activity enough for session replay and cost/context
awareness without treating full subagent transcripts as ordinary main-thread
conversation history.

#### Scenario: Subagent lifecycle event is emitted

- **WHEN** a subagent starts, completes, fails, or requires approval
- **THEN** Deepy SHALL record a replay-safe event or item representing that
  lifecycle state
- **AND** replay SHALL render the lifecycle event without requiring the subagent
  to run again

#### Scenario: Subagent returns a result

- **WHEN** a subagent returns a final report to the main agent
- **THEN** Deepy SHALL preserve the report needed for the main agent's
  continuation and session replay
- **AND** it SHALL avoid duplicating the entire nested subagent transcript into
  the main session context unless explicitly required for correctness

#### Scenario: Subagent usage is known

- **WHEN** subagent token usage is available from the SDK run result
- **THEN** Deepy SHOULD account for that usage in session usage reporting
- **AND** it SHOULD distinguish subagent usage from main-agent usage when the
  data is available
