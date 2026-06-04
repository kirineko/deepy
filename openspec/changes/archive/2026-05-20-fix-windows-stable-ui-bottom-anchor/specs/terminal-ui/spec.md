## ADDED Requirements

### Requirement: Stable Windows Prompt Bottom Anchor

Deepy's stable prompt-toolkit terminal UI SHALL preserve submitted prompt
transcript visibility on Windows when active work starts immediately after a
prompt submitted from the terminal bottom.

#### Scenario: Windows submitted prompt reaches terminal bottom

- **WHEN** the user runs the stable terminal UI in Windows Terminal or another
  Windows console-backed TTY
- **AND** the user submits a non-empty prompt whose transcript copy would start
  active work while the cursor is on the final visible terminal row
- **THEN** Deepy SHALL detect that bottom-row cursor position on Windows
- **AND** it SHALL create scrollable transcript space before drawing the runtime
  status row
- **AND** the submitted prompt transcript copy SHALL remain visible above the
  runtime status row

#### Scenario: Windows submitted prompt is not at terminal bottom

- **WHEN** the user runs the stable terminal UI in a Windows console-backed TTY
- **AND** the user submits a non-empty prompt while the cursor is not on the
  final visible terminal row
- **THEN** Deepy SHALL NOT add bottom-anchor scroll space solely because the
  platform is Windows
- **AND** normal transcript output SHALL continue from the current cursor
  position

#### Scenario: Windows cursor position cannot be read

- **WHEN** Deepy cannot read the Windows console cursor position for a stable UI
  prompt submission
- **THEN** Deepy SHALL continue the turn without crashing
- **AND** it SHALL keep the runtime status row clearable at turn completion
- **AND** any fallback bottom-anchor behavior SHALL be limited to Windows TTY
  submissions where preserving transcript visibility is more important than
  avoiding one extra blank line

#### Scenario: POSIX terminal behavior is preserved

- **WHEN** the user runs the stable terminal UI in a POSIX terminal
- **AND** the terminal supports the existing ANSI cursor report path
- **THEN** Deepy SHALL continue using that path for bottom-anchor detection
- **AND** the Windows cursor detection path SHALL NOT run
