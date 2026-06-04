## ADDED Requirements

### Requirement: Textual TUI Polish Documentation
Deepy documentation SHALL describe the polished Textual TUI experience without
claiming that the stable UI has been removed or replaced.

#### Scenario: User reads TUI documentation
- **WHEN** documentation describes `deepy tui`
- **THEN** it SHALL explain the compact transcript, integrated composer,
  attachment deletion, live activity feedback, and inline decision blocks
- **AND** it SHALL state that `deepy` remains the current default entrypoint

#### Scenario: User reads theme documentation
- **WHEN** documentation describes UI themes
- **THEN** it SHALL explain that Deepy's shared theme values remain `dark` and
  `light`
- **AND** it SHALL document the Textual TUI's curated built-in theme mapping
- **AND** it SHALL document that the Textual TUI can save a TUI-specific
  `ui.textual_theme` override from the theme picker
- **AND** it SHALL distinguish any TUI-specific Textual theme selection from the
  stable UI theme contract

#### Scenario: Documentation includes screenshots
- **WHEN** documentation includes TUI screenshots after this change
- **THEN** screenshots SHALL show the current polished layout
- **AND** stale screenshots of the previous TUI layout SHALL be removed or
  clearly replaced
