## ADDED Requirements

### Requirement: Bottom Context Status Accuracy

Deepy's bottom toolbar SHALL represent current session context pressure using the same effective token state used for automatic compaction.

#### Scenario: Latest turn is short

- **WHEN** a session has existing context and the user sends a short follow-up prompt
- **THEN** the bottom toolbar context status SHALL NOT shrink merely because the latest API usage input tokens are lower than the previous turn
- **AND** it SHALL continue to show the effective context pressure for the active session

#### Scenario: Context state is near compaction threshold

- **WHEN** effective session context tokens are at or above the configured compact threshold
- **THEN** the bottom toolbar SHALL indicate compaction pressure using that effective token count
- **AND** the displayed pressure SHALL match the token source used by automatic compaction decisions

#### Scenario: Explicit compaction reduces context

- **WHEN** manual or automatic compaction rewrites the active session
- **THEN** the bottom toolbar MAY show a lower context token count
- **AND** the lower count SHALL be based on the compacted replacement history
