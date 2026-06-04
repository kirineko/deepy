## ADDED Requirements

### Requirement: File Mutation Preflight Approval
Deepy SHALL show proposed file mutation diffs before resolving normal-mode
`Write` and `Update` approval interruptions.

#### Scenario: Normal mode shows proposed write diff before approval
- **WHEN** the active audit mode is `normal`
- **AND** the model requests a `Write` mutation that requires approval
- **THEN** Deepy SHALL compute a preflight diff before approving or rejecting
  the SDK interruption
- **AND** the active UI SHALL show the proposed diff outside the approval
  decision control
- **AND** the file SHALL NOT be mutated before the user approves

#### Scenario: Normal mode shows proposed update diff before approval
- **WHEN** the active audit mode is `normal`
- **AND** the model requests an `Update` mutation that requires approval
- **THEN** Deepy SHALL compute a preflight diff before approving or rejecting
  the SDK interruption
- **AND** the active UI SHALL show the proposed diff outside the approval
  decision control
- **AND** the file SHALL NOT be mutated before the user approves

#### Scenario: User rejects proposed file mutation
- **WHEN** a proposed file mutation diff is shown
- **AND** the user rejects the approval
- **THEN** Deepy SHALL reject the SDK interruption
- **AND** Deepy SHALL leave the proposed diff visible as rejected review context
- **AND** Deepy SHALL NOT mutate the target files

#### Scenario: Approved proposed file mutation does not duplicate the diff
- **WHEN** a proposed file mutation diff is shown
- **AND** the user approves the approval
- **AND** the approved tool execution reports the same diff
- **THEN** Deepy SHALL NOT render the same diff a second time after execution

#### Scenario: Non-normal file mutation behavior is unchanged
- **WHEN** the active audit mode is `auto` or `yolo`
- **AND** the model requests `Write` or `Update`
- **THEN** Deepy SHALL preserve the existing approval behavior for that mode
- **AND** Deepy SHALL NOT require an extra preflight approval step
