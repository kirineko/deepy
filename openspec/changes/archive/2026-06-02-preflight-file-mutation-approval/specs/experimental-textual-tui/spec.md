## ADDED Requirements

### Requirement: Modern UI Proposed File Changes
Modern UI SHALL render preflighted file mutation diffs in the transcript before
asking for a normal-mode approval decision.

#### Scenario: Proposed diff appears before file approval
- **WHEN** a normal-mode `Write` or `Update` approval requires a preflight diff
- **THEN** Modern UI SHALL append a proposed file change block to the transcript
- **AND** it SHALL show the approval decision in the bottom interaction sheet
- **AND** the decision sheet SHALL NOT contain the large diff preview

#### Scenario: Proposed diff records rejection
- **WHEN** the user rejects a proposed file mutation in Modern UI
- **THEN** the proposed change block SHALL remain in the transcript
- **AND** it SHALL show a rejected state
