## ADDED Requirements

### Requirement: Prompt-Toolkit Input Footer Ownership

Deepy SHALL use prompt-toolkit as the owner of interactive prompt input layout
and the compact idle footer.

#### Scenario: Idle prompt is shown

- **WHEN** Deepy prompts for interactive user input
- **THEN** the prompt bottom footer SHALL be rendered through prompt-toolkit
  `bottom_toolbar`
- **AND** the footer SHALL show compact status segments for the active model and
  reasoning mode, CWD, loaded project instructions, MCP status, and context
  window status when available
- **AND** the footer SHALL show the newline hint `newline: ctrl+j`
- **AND** the footer SHALL NOT show persistent `Ctrl+D twice exit` help

#### Scenario: Multiline input grows near terminal bottom

- **WHEN** user input spans multiple lines near the terminal bottom
- **THEN** prompt-toolkit SHALL keep the editable input area bounded
- **AND** the prompt footer SHALL remain owned by prompt-toolkit
- **AND** Deepy SHALL NOT use an additional ANSI scroll-region footer renderer
  to reserve terminal-bottom rows

#### Scenario: Runtime status is deferred

- **WHEN** a model turn or interactive local command is running
- **THEN** Deepy SHALL NOT start a competing ANSI scroll-region footer renderer
- **AND** completed transcript output SHALL continue to be printed through the
  normal Rich transcript path
- **AND** live runtime status display SHALL be handled by a follow-up global TUI
  change rather than by this archived change

## MODIFIED Requirements

### Requirement: Persistent Interactive Status Footer

Deepy SHALL keep a compact interactive status footer visible during idle
interactive prompt input, with prompt-toolkit owning footer placement.

#### Scenario: Idle prompt is shown

- **WHEN** Deepy prompts for interactive user input
- **THEN** the prompt bottom footer SHALL show compact status segments for the active model and reasoning mode, CWD, and context window status
- **AND** the model and reasoning mode SHALL be represented as a single leading segment such as `model deepseek-v4-pro[max]`
- **AND** the footer SHALL NOT show a separate `thinking` label segment for reasoning mode
- **AND** the footer SHALL NOT show persistent `Ctrl+D twice exit` help
- **AND** the footer SHALL show the newline hint `newline: ctrl+j`
