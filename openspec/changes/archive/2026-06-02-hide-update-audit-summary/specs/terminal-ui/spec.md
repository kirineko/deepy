## MODIFIED Requirements

### Requirement: File Mutation Approval Diff Review

Deepy's stable terminal UI SHALL render `Write` and `Update` audit approvals
with highlighted diff previews and relative target paths when possible.

#### Scenario: Missing update diff context uses safe fallback

- **WHEN** an `Update` approval does not contain enough before-and-after
  information to derive a reliable diff
- **THEN** Deepy SHALL show a compact typed summary instead of fabricating a diff
- **AND** it SHALL still display the target path using the relative-path rules
- **AND** the typed summary SHALL show the number of edits when available
- **AND** it SHALL NOT show a structured `summary` argument block or raw old/new
  argument content
