## ADDED Requirements

### Requirement: Status Usage Scopes
Deepy SHALL report Token Usage in `/status` using explicit local scopes while preserving the existing separation between cumulative API usage and latest request Context Window occupancy.

#### Scenario: Active session usage is known
- **WHEN** the user runs `/status`
- **AND** an active session exists with persisted Token Usage
- **THEN** Deepy SHALL show active-session Token Usage as cumulative API consumption for that session
- **AND** it SHALL include known request count, input, output, cache, reasoning, and total token fields in compact form

#### Scenario: Project usage is known
- **WHEN** the user runs `/status`
- **AND** the project session index contains persisted Token Usage for one or more sessions
- **THEN** Deepy SHALL show project-level Token Usage by merging known session usage records
- **AND** it SHALL treat sessions without usage metadata as unknown rather than inventing usage

#### Scenario: Context window status is shown
- **WHEN** the user runs `/status`
- **AND** latest request Context Window usage is known for the active session
- **THEN** Deepy SHALL show Context Window used tokens, total context window tokens, remaining tokens, and percentage
- **AND** it SHALL NOT substitute cumulative Token Usage totals as Context Window used tokens

#### Scenario: Usage is unavailable
- **WHEN** the user runs `/status`
- **AND** active-session or project Token Usage is not known
- **THEN** Deepy SHALL render that usage scope as unknown or unavailable
- **AND** it SHALL keep the rest of the status panel visible
