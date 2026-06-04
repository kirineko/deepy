## ADDED Requirements

### Requirement: Textual UI Migration Documentation
Deepy documentation SHALL describe the redesigned Textual TUI direction without
claiming that the stable UI has already been removed or replaced.

#### Scenario: UI topic docs are updated
- **WHEN** UI documentation is updated for this change
- **THEN** English and Chinese docs SHALL explain that `deepy` remains the
  current stable default entrypoint
- **AND** they SHALL explain that `deepy tui` is being redesigned as the future
  primary UI candidate
- **AND** they SHALL describe the staged migration goal to eventually remove
  stable/TUI duplication

#### Scenario: Composer behavior is documented
- **WHEN** docs describe the redesigned Textual composer
- **THEN** they SHALL explain prompt text, image attachments, generated input
  suggestions, slash suggestions, and file suggestions as distinct UI states
- **AND** they SHALL NOT describe attachment state as text replacement tokens
  inside the prompt buffer

#### Scenario: Screenshots are updated
- **WHEN** screenshots or visual assets are kept, replaced, or removed for the
  redesigned TUI
- **THEN** docs SHALL reference only existing assets
- **AND** stale screenshots of the old TUI layout SHALL be removed or clearly
  replaced
