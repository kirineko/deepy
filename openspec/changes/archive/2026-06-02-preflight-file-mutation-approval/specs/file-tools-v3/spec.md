## ADDED Requirements

### Requirement: V3 File Mutation Preflight
Deepy's v3 file mutation tools SHALL expose an internal preflight planning path
that predicts the mutation diff without committing side effects.

#### Scenario: Write preflight matches actual write diff
- **WHEN** Deepy preflights a valid `Write` mutation
- **THEN** the preflight result SHALL include the same unified diff that the
  approved `Write` tool execution would report for the same file state
- **AND** the preflight SHALL NOT write or create the target file

#### Scenario: Update preflight matches actual update diff
- **WHEN** Deepy preflights a valid `Update` mutation
- **THEN** the preflight result SHALL include the same unified diff that the
  approved `Update` tool execution would report for the same file state
- **AND** the preflight SHALL NOT write the target files

#### Scenario: Preflight preserves mutation guardrails
- **WHEN** a `Write` or `Update` mutation would fail path policy, stale snapshot,
  unsupported target, invalid argument, or exact-match validation
- **THEN** the preflight result SHALL report the blocking error
- **AND** it SHALL NOT provide an approval path that bypasses the guardrail
