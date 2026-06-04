## ADDED Requirements

### Requirement: Shared Theme Contract With Textual Theme Mapping
Deepy SHALL preserve the shared `dark` and `light` UI theme contract while
allowing the Textual TUI to map those values to richer Textual-native themes.

#### Scenario: Stable UI reads theme settings
- **WHEN** the default stable terminal UI reads `ui.theme`
- **THEN** it SHALL continue to accept `dark` and `light`
- **AND** it SHALL NOT be required to understand Textual-only theme names

#### Scenario: Textual TUI reads theme settings
- **WHEN** the Textual TUI reads `ui.theme`
- **THEN** it MAY map `dark` and `light` to curated Textual built-in themes
- **AND** the mapping SHALL remain internal to the Textual TUI unless a separate
  TUI-specific config field is introduced
- **AND** the default `dark` mapping SHALL use `tokyo-night`

#### Scenario: Textual TUI reads a TUI-specific theme override
- **WHEN** `ui.textual_theme` contains a supported Textual theme name
- **THEN** the Textual TUI MAY apply that theme instead of the shared
  `ui.theme` mapping
- **AND** the stable UI SHALL ignore the TUI-specific theme override

#### Scenario: User selects shared theme
- **WHEN** the user selects `/theme dark` or `/theme light`
- **THEN** Deepy SHALL persist the selected shared theme value
- **AND** both the stable UI and Textual TUI SHALL be able to start with a
  readable theme from that value

#### Scenario: User selects a Textual-only TUI theme
- **WHEN** the user selects a supported Textual-only theme in the Textual TUI
- **THEN** Deepy SHALL persist the selected Textual theme in a TUI-specific
  config field
- **AND** it SHALL preserve the shared `ui.theme` value for stable UI
  compatibility
