## ADDED Requirements

### Requirement: Modern UI shall render command-mode local command results without unnecessary noise

The Modern UI MUST render `!cmd` results in the transcript without calling the
model, and successful commands MUST NOT display a redundant `exit 0` metadata
line. Failed commands MUST still expose their non-zero exit code.

#### Scenario: Successful local command hides exit-zero metadata

- **GIVEN** a user submits `!pwd`
- **WHEN** the command exits with code `0`
- **THEN** the Modern UI transcript shows the command output
- **AND** the local command metadata does not include `exit 0`

#### Scenario: Failed local command keeps non-zero exit metadata

- **GIVEN** a user submits a local command that exits with code `2`
- **WHEN** the result is rendered in Modern UI
- **THEN** the transcript metadata includes `exit 2`

### Requirement: Modern UI shall keep bottom-sheet picker options readable

The Modern UI MUST make bottom-sheet `OptionList` choices readable across
supported Textual themes, including provider, model, theme, audit, and
ask-user-question flows.

#### Scenario: Inline picker options remain visible

- **GIVEN** a bottom-sheet picker is opened for provider/model style selection
- **WHEN** options are mounted
- **THEN** option text, highlighted option text, and disabled option text have
  explicit readable styles
- **AND** the option list is not visually blank.

#### Scenario: Inline command picker returns stable option values

- **GIVEN** a user submits `/ui` without an argument
- **WHEN** the user selects the Classic UI option from the bottom-sheet picker
- **THEN** the Modern UI persists `classic` as the configured UI interface
- **AND** the transcript does not show a `/ui classic|modern` usage error.
