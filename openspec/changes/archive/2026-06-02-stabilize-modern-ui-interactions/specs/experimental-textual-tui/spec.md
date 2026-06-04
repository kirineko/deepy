## ADDED Requirements

### Requirement: Modern UI Blocking Interactions
Modern UI SHALL keep bottom-sheet decision flows keyboard-completable even when
the transcript or prompt attempts to regain focus.

#### Scenario: Audit decision owns keyboard focus
- **WHEN** an audit approval decision is pending in Modern UI
- **AND** the prompt would otherwise receive focus or an `Esc` key
- **THEN** the pending audit decision SHALL keep keyboard ownership
- **AND** `Esc` SHALL reject the pending audit decision
- **AND** the prompt SHALL NOT consume keys that leave the audit decision
  unresolved

#### Scenario: Ask-user-question owns keyboard focus
- **WHEN** an ask-user-question response is pending in Modern UI
- **AND** the prompt would otherwise receive focus or an `Esc` key
- **THEN** the pending question flow SHALL keep keyboard ownership
- **AND** `Esc` SHALL cancel or decline the pending question flow
- **AND** the prompt SHALL NOT consume keys that leave the question unresolved

### Requirement: Modern UI Diff Ordering And Scrolling
Modern UI SHALL render file mutation diffs in chronological transcript order
without breaking conversation scrolling.

#### Scenario: Diff replaces compact mutation output
- **WHEN** a `Write` or `Update` tool output contains diff metadata
- **THEN** Modern UI SHALL render the diff block at the tool output position
- **AND** it SHALL NOT leave a separate compact output row for the same mutation
- **AND** later tool outputs SHALL remain after the diff block

#### Scenario: Diff precedes streamed mutation summary
- **WHEN** Modern UI has already rendered streamed assistant text in the current
  turn
- **AND** a later `Write` or `Update` tool output contains diff metadata
- **THEN** Modern UI SHALL place the diff block before the current assistant
  text block
- **AND** it SHALL NOT duplicate the compact mutation output row

#### Scenario: Large diff remains scroll-safe
- **WHEN** a rendered diff is larger than the visible transcript region
- **THEN** Modern UI SHALL keep transcript scrolling functional
- **AND** prompt history navigation SHALL NOT be the only available scroll
  behavior

### Requirement: Modern UI Composer Ergonomics
Modern UI SHALL provide a multi-line composer that remains usable for longer
prompts.

#### Scenario: Composer has five visible prompt lines
- **WHEN** Modern UI is idle
- **THEN** the prompt composer SHALL reserve five visible input lines
- **AND** status, attachment, and hint rows SHALL remain visible without overlap

#### Scenario: Long draft scrolls inside composer
- **WHEN** the prompt draft exceeds five visible lines
- **THEN** the prompt input SHALL allow the user to scroll or navigate within
  the draft
- **AND** it SHALL NOT expand in a way that hides the transcript or status bar

### Requirement: Modern UI Dense Markdown Output
Modern UI SHALL render Markdown tables and adjacent transcript blocks with
terminal-appropriate density.

#### Scenario: Table output is compact
- **WHEN** assistant or tool output contains a Markdown table
- **THEN** Modern UI SHALL render the table without excessive vertical padding
- **AND** surrounding transcript spacing SHALL remain compact and readable
