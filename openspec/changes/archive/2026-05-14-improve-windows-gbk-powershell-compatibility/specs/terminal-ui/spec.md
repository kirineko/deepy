## ADDED Requirements

### Requirement: Windows Terminal Shift Enter Newline

Deepy SHALL support Shift+Enter newline insertion in Windows Terminal when running under PowerShell 7 without changing Enter submission behavior.

#### Scenario: Windows Terminal Shift Enter inserts newline

- **WHEN** the user runs Deepy in Windows Terminal with PowerShell 7
- **AND** the user presses Shift+Enter in the prompt input
- **THEN** Deepy SHALL insert a newline into the current prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: Windows Terminal Enter submits

- **WHEN** the user runs Deepy in Windows Terminal with PowerShell 7
- **AND** the user presses Enter without Shift in the prompt input
- **THEN** Deepy SHALL submit the current prompt

#### Scenario: Existing POSIX terminal newline sequences still work

- **WHEN** the user runs Deepy in a POSIX terminal that emits a supported Shift+Enter escape sequence
- **AND** the user presses Shift+Enter in the prompt input
- **THEN** Deepy SHALL continue to insert a newline into the current prompt buffer
