## ADDED Requirements

### Requirement: Textual Command Surfaces
The experimental Textual TUI SHALL provide Textual-native command discovery and
auxiliary command surfaces while preserving slash command entry from the prompt.

#### Scenario: User opens command discovery
- **WHEN** a user opens command discovery in the experimental TUI
- **THEN** the TUI SHALL show available commands grouped by purpose
- **AND** each command SHALL include a concise label and description
- **AND** selecting a command SHALL either run it or open the appropriate
  Textual screen, modal, or form

#### Scenario: User types a slash command
- **WHEN** a user types `/` at the beginning of the TUI prompt
- **THEN** the TUI SHALL provide prompt-adjacent slash command suggestions
- **AND** selecting a suggestion SHALL insert the command without submitting
  unrelated prompt text

#### Scenario: Command is not implemented in TUI yet
- **WHEN** a user invokes a stable Deepy slash command that is not yet
  implemented in the experimental TUI
- **THEN** the TUI SHALL show a clear TUI-specific unsupported message
- **AND** it SHALL NOT silently ignore the command or start a model turn

### Requirement: Textual Question Continuation
The experimental Textual TUI SHALL complete AskUserQuestion continuation without
requiring the user to exit to the stable terminal UI.

#### Scenario: Pending question is returned
- **WHEN** a model turn completes with pending AskUserQuestion questions
- **THEN** the TUI SHALL render an interactive question surface
- **AND** the question surface SHALL receive focus automatically
- **AND** the active session id SHALL be preserved for continuation

#### Scenario: User selects predefined answers
- **WHEN** the pending question contains predefined options
- **THEN** the TUI SHALL allow keyboard navigation and selection
- **AND** it SHALL support both single-select and multi-select questions
- **AND** submitting the answer SHALL continue the same session with the
  selected answer content

#### Scenario: User provides a custom answer
- **WHEN** the pending question includes a custom-answer option or the user
  chooses to answer freely
- **THEN** the TUI SHALL collect custom text in the question surface
- **AND** it SHALL submit that text as the user's answer for continuation

#### Scenario: User cancels a pending question
- **WHEN** the user cancels the question surface
- **THEN** the TUI SHALL leave the session in a recoverable state
- **AND** it SHALL show that the question was cancelled instead of pretending
  the model turn completed normally

### Requirement: Mature Transcript Interaction
The experimental Textual TUI SHALL provide navigable transcript behavior that
does not fight user scroll position during live output.

#### Scenario: User is anchored at transcript bottom
- **WHEN** new assistant, thinking, tool, or diff output arrives while the
  transcript is anchored at the bottom
- **THEN** the TUI SHALL keep the newest output visible
- **AND** live block growth SHALL remain readable

#### Scenario: User scrolls away from transcript bottom
- **WHEN** the user has intentionally scrolled up in the transcript
- **THEN** new output SHALL NOT force the transcript back to the bottom
- **AND** the TUI SHALL provide a visible indication that new output is available

#### Scenario: User navigates transcript blocks
- **WHEN** the transcript contains multiple focusable blocks
- **THEN** the user SHALL be able to move between blocks by keyboard
- **AND** expandable blocks SHALL preserve focus and scroll position when
  expanded or collapsed

#### Scenario: User recalls input history
- **WHEN** the prompt is focused and input history exists
- **THEN** the TUI SHALL allow the user to navigate previous prompts without
  corrupting the current draft

### Requirement: Textual Diff Interaction
The experimental Textual TUI SHALL make Deepy-owned diff previews usable across
narrow and wide terminal layouts.

#### Scenario: Diff contains long changed lines
- **WHEN** a TUI diff block contains lines wider than the available terminal
  width
- **THEN** the diff view SHALL wrap or fold the lines inside the block
- **AND** line gutters and added/removed styling SHALL remain associated with
  the correct changed content

#### Scenario: Diff contains multiple hunks
- **WHEN** a TUI diff block contains multiple hunks
- **THEN** the diff view SHALL expose hunk boundaries
- **AND** the user SHALL be able to navigate between hunks by keyboard
- **AND** the user SHALL be able to fold and unfold hunk detail

#### Scenario: Terminal width supports richer diff layout
- **WHEN** the terminal is wide enough for an enhanced diff layout
- **THEN** the TUI MAY show a side-by-side or expanded layout
- **AND** it SHALL preserve a readable single-column fallback for narrower
  terminals

### Requirement: Textual Responsive Visual Quality
The experimental Textual TUI SHALL preserve a polished, non-overlapping layout
across common terminal sizes.

#### Scenario: TUI runs in a narrow terminal
- **WHEN** the experimental TUI runs in a narrow terminal
- **THEN** the app SHALL prioritize a single-column conversation layout
- **AND** auxiliary views SHALL open as modal screens or full-width surfaces
- **AND** text SHALL wrap, fold, or truncate intentionally without overlapping
  adjacent UI elements

#### Scenario: TUI runs in a wide terminal
- **WHEN** the experimental TUI runs in a wide terminal
- **THEN** the app MAY show a side panel for status, todos, project context, or
  command detail
- **AND** hiding or showing the side panel SHALL NOT disturb active prompt input
  or transcript focus

#### Scenario: TUI renders tool and thinking labels
- **WHEN** the TUI renders thinking blocks and tool activity
- **THEN** it SHALL use a shared label style family for labels
- **AND** it SHALL use semantic state styling rather than unrelated per-tool
  colors
