## MODIFIED Requirements

### Requirement: Instruction Status Indicator

Deepy SHALL show a compact terminal status indicator when AGENTS.md instructions apply to the current project.

#### Scenario: Applicable instructions exist

- **WHEN** Deepy builds the interactive status footer and global or project `AGENTS.md` instructions are non-empty and applicable
- **THEN** the footer SHALL include the exact compact indicator `[AGENTS.md]`
- **AND** the indicator SHALL preserve the exact case-sensitive filename `AGENTS.md`
- **AND** the footer SHALL NOT show the verbose indicator `AGENTS.md loaded`

#### Scenario: No applicable instructions exist

- **WHEN** Deepy builds the interactive status footer and no global or project `AGENTS.md` instructions are applicable
- **THEN** the footer SHALL NOT show the AGENTS.md rules indicator
