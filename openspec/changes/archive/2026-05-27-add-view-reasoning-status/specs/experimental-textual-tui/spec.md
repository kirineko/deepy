## ADDED Requirements

### Requirement: Textual View Mode And Stream Status
The experimental Textual TUI SHALL mirror the stable terminal UI's view mode and current-turn stream token status semantics.

#### Scenario: Textual TUI starts with concise view
- **WHEN** the experimental TUI starts and the resolved UI view mode is `concise`
- **THEN** live reasoning transcript blocks SHALL be hidden by default
- **AND** provider reasoning behavior SHALL remain unchanged

#### Scenario: Textual TUI starts with full view
- **WHEN** the experimental TUI starts and the resolved UI view mode is `full`
- **THEN** live reasoning transcript blocks SHALL be shown
- **AND** provider reasoning behavior SHALL remain unchanged

#### Scenario: Textual user toggles view mode
- **WHEN** a user invokes `/view` or `/view toggle` in the experimental TUI
- **THEN** the TUI SHALL switch between `concise` and `full`
- **AND** it SHALL persist the new view mode to TOML
- **AND** it SHALL update in-memory view mode for subsequent live output
- **AND** it SHALL show a concise confirmation that includes whether reasoning is hidden or shown

#### Scenario: Textual model turn is running
- **WHEN** a model turn is in progress in the experimental TUI
- **THEN** the TUI SHALL show live progress with elapsed time when available
- **AND** when streamed reasoning, assistant output text, or streamed tool-call argument text has been received in the current model turn, the TUI SHALL show a current-turn cumulative stream token estimate formatted as `↓ N tokens`
- **AND** the estimate SHALL continue accumulating across streamed reasoning, assistant output, and streamed tool-call argument deltas in the same model turn
- **AND** token estimates of at least 1000 SHALL use compact `K` suffix formatting such as `↓ 1.1K tokens`
- **AND** this `K`-only formatting SHALL apply only to the runtime stream token estimate, not to the context-window `ctx` segment
- **AND** the estimate SHALL reset at the start of each model turn
- **AND** the estimate SHALL remain separate from final provider usage accounting

#### Scenario: Textual user provides invalid view command
- **WHEN** a user invokes `/view` with an argument other than `toggle`, `concise`, or `full` in the experimental TUI
- **THEN** the TUI SHALL show a concise usage message
- **AND** it SHALL keep the saved view mode unchanged
