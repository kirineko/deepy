## ADDED Requirements

### Requirement: Classic UI source package

The default prompt-toolkit terminal UI SHALL live under `deepy.ui.classic` and share
primitives through `deepy.ui.shared`.

#### Scenario: Maintainer imports the classic terminal loop

- **WHEN** code loads the default interactive UI
- **THEN** it SHALL import from `deepy.ui.classic` (for example
  `deepy.ui.classic.terminal`)
- **AND** shared rendering, session, and input helpers SHALL be imported from
  `deepy.ui.shared` rather than duplicating them under `deepy.ui.classic`

#### Scenario: Package boundary exports stable entry points

- **WHEN** external code imports `deepy.ui`
- **THEN** it SHALL be able to reach `run_interactive` and `run_tui` without
  importing removed top-level UI modules such as `deepy.ui.terminal` or `deepy.tui`
