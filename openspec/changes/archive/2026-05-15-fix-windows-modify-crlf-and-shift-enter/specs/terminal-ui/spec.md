## ADDED Requirements

### Requirement: Windows Terminal Ctrl J Newline

Deepy SHALL support Ctrl+J as the Windows Terminal multiline newline key when running under PowerShell 7, and SHALL make that shortcut visible in Windows prompt UI guidance.

#### Scenario: Windows Terminal Ctrl J inserts newline

- **WHEN** the user runs Deepy in Windows Terminal with PowerShell 7
- **AND** the user presses Ctrl+J in the prompt input
- **THEN** Deepy SHALL insert a newline into the current prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: Windows Terminal Enter submits

- **WHEN** the user runs Deepy in Windows Terminal with PowerShell 7
- **AND** the user presses Enter in the prompt input
- **THEN** Deepy SHALL submit the current prompt

#### Scenario: Windows prompt toolbar shows Ctrl J

- **WHEN** Deepy renders prompt input guidance on Windows
- **THEN** the toolbar or equivalent prompt help SHALL mention Ctrl+J as the newline shortcut
- **AND** it SHALL NOT advertise Shift+Enter as the Windows newline shortcut

#### Scenario: Existing POSIX terminal newline sequences still work

- **WHEN** the user runs Deepy in a POSIX terminal that emits a supported Shift+Enter escape sequence
- **AND** the user presses Shift+Enter in the prompt input
- **THEN** Deepy SHALL continue to insert a newline into the current prompt buffer

## REMOVED Requirements

### Requirement: Windows Terminal Shift Enter Newline

**Reason**: Windows user testing showed Ctrl+J works reliably while Shift+Enter remains ineffective in Windows Terminal under PowerShell 7. Maintaining Windows-specific Shift+Enter interception adds complexity without satisfying the tested workflow.

**Migration**: Use Ctrl+J for multiline input on Windows. Keep Enter for submit. Retain non-Windows Shift+Enter escape-sequence behavior where the terminal emits a supported distinguishable sequence.
