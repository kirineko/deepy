## ADDED Requirements

### Requirement: Theme-Aware Rendering

Deepy SHALL render terminal UI using a selected theme palette so content remains
readable in both light-background and dark-background terminals.

#### Scenario: User uses a light-background terminal

- **WHEN** the active UI theme resolves to `light`
- **THEN** Deepy SHALL render welcome text, panels, user messages, assistant
  messages, muted status text, thinking/progress summaries, tool panels, and
  diff/write previews with colors that remain legible on a light background

#### Scenario: User uses a dark-background terminal

- **WHEN** the active UI theme resolves to `dark`
- **THEN** Deepy SHALL render welcome text, panels, user messages, assistant
  messages, muted status text, thinking/progress summaries, tool panels, and
  diff/write previews with colors that remain legible on a dark background

#### Scenario: Assistant output contains Markdown tables

- **WHEN** assistant output includes a valid Markdown pipe table
- **THEN** Deepy SHALL render the table with aligned columns and visible cell
  boundaries
- **AND** long table cells SHALL wrap inside the table for the current terminal
  width instead of relying on uncontrolled terminal line wrapping

#### Scenario: User selects automatic theme

- **WHEN** the saved UI theme is `auto`
- **THEN** Deepy SHALL resolve the runtime palette from terminal background
  information when available
- **AND** it SHALL fall back to a readable dark-compatible palette when reliable
  background information is unavailable

#### Scenario: User changes theme inside an interactive session

- **WHEN** a user runs `/theme light`, `/theme dark`, or `/theme auto`
- **THEN** Deepy SHALL persist the selected theme
- **AND** subsequent interactive output SHALL use the selected theme
- **AND** it SHALL advise the user to restart Deepy so the theme applies
  everywhere

#### Scenario: User chooses theme inside an interactive session

- **WHEN** a user runs `/theme` without an argument
- **THEN** Deepy SHALL show the current saved theme once
- **AND** it SHALL show keyboard-selectable `auto`, `dark`, and `light` theme
  choices
- **AND** fallback non-picker flows SHALL accept a selected theme by number or
  name
- **AND** it SHALL advise the user to restart Deepy after persisting the
  selected theme

#### Scenario: User provides an invalid interactive theme

- **WHEN** a user runs `/theme` with a value other than `auto`, `dark`, or `light`
- **THEN** Deepy SHALL reject the value with a concise usage message
- **AND** it SHALL keep the previously saved theme

#### Scenario: User resets configuration inside an interactive session

- **WHEN** a user runs `/reset`
- **THEN** Deepy SHALL delete the existing TOML config file when it exists
- **AND** it SHALL guide the user through interactive setup again
- **AND** subsequent interactive output SHALL use the newly saved UI theme

## MODIFIED Requirements

### Requirement: Startup Screen

Deepy SHALL show a compact welcome panel.

#### Scenario: User starts interactive mode

- **WHEN** Deepy starts
- **THEN** the welcome panel SHALL show the Deepy identity, version, model,
  thinking settings, CWD, active UI theme, and only core commands

#### Scenario: First interactive startup has no saved theme

- **WHEN** Deepy starts interactive mode and no valid UI theme is saved
- **THEN** Deepy SHALL show numbered `auto`, `dark`, and `light` theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL persist the choice before rendering the welcome panel
- **AND** the welcome panel SHALL use the selected theme
