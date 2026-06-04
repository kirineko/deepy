## ADDED Requirements

### Requirement: Modern UI source package

The experimental Textual TUI implementation SHALL live under `deepy.ui.modern` and
MUST NOT depend on a separate top-level `deepy.tui` package.

#### Scenario: Maintainer imports the TUI app

- **WHEN** code loads the Textual application entry point
- **THEN** it SHALL import from `deepy.ui.modern` (for example `deepy.ui.modern.app`
  or `deepy.ui.modern.runner`)
- **AND** the repository SHALL NOT ship `deepy.tui` as an installable package path

#### Scenario: User starts the experimental TUI

- **WHEN** a user runs `deepy tui`
- **THEN** Deepy SHALL start the Textual UI through `deepy.ui.modern` without
  importing `deepy.tui`
