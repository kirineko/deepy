## ADDED Requirements

### Requirement: Textual Primary UI Candidate
The experimental Textual TUI SHALL be redesigned as Deepy's future primary
terminal UI candidate while remaining opt-in for this change.

#### Scenario: Textual TUI identifies the migration stage
- **WHEN** a user starts `deepy tui`
- **THEN** the UI SHALL present itself as the redesigned Textual experience
- **AND** it SHALL NOT claim that the stable UI has already been removed
- **AND** it SHALL preserve the current opt-in entrypoint for this change

#### Scenario: Stable UI remains available during redesign
- **WHEN** a user runs `deepy`
- **THEN** Deepy SHALL continue to start the existing stable interactive UI
- **AND** Textual redesign work SHALL NOT break the stable UI entrypoint

### Requirement: Compact Textual Shell
The redesigned Textual TUI SHALL use a compact terminal-agent shell that keeps
conversation content primary and avoids persistent heavy dashboard chrome.

#### Scenario: User opens the redesigned TUI
- **WHEN** the Textual TUI is idle
- **THEN** the transcript SHALL occupy the main scrollback region
- **AND** the UI SHALL show a lightweight status line with model, project, audit,
  MCP, and context information when available
- **AND** the composer SHALL sit at the bottom of the viewport
- **AND** persistent header, footer, sidebar, or card chrome SHALL NOT consume
  space unless it is required for an active workflow

#### Scenario: Composer grows for multiline input
- **WHEN** a user enters multiple prompt lines
- **THEN** the composer SHALL grow within a bounded maximum height
- **AND** the transcript SHALL remain readable above the composer
- **AND** text SHALL NOT overlap the status line, suggestions, or transcript

#### Scenario: Auxiliary UI appears on demand
- **WHEN** a user opens help, status, model selection, skills, sessions, file
  suggestions, slash suggestions, or approval review
- **THEN** the TUI SHALL present the auxiliary UI as an overlay, modal, picker,
  or bounded panel
- **AND** closing it SHALL return focus to the composer or previous conversation
  context without losing transcript position

### Requirement: Native Textual Composer
The Textual composer SHALL keep the editable prompt buffer limited to
user-authored text and SHALL render structured prompt state through Textual UI
surfaces.

#### Scenario: User types normal prompt text
- **WHEN** a user types text into the Textual composer
- **THEN** the underlying prompt buffer SHALL contain exactly the user-authored
  text
- **AND** Deepy SHALL NOT insert UI-only replacement tokens into the prompt
  buffer

#### Scenario: User accepts generated input suggestion
- **WHEN** a generated input suggestion is visible for an empty composer
- **AND** the user accepts it with the supported keybinding
- **THEN** the accepted suggestion SHALL become prompt text
- **AND** the suggestion preview SHOULD use Textual-native suggestion behavior
  rather than a separate fixed ghost-text row

#### Scenario: Slash suggestions are visible
- **WHEN** a user types a slash command prefix at the beginning of the composer
- **THEN** the TUI SHALL show matching slash commands in a selectable Textual
  suggestion surface
- **AND** the suggestion surface SHALL NOT insert description text into the
  prompt buffer
- **AND** accepting a command SHALL insert only the command token and any
  required spacing into the prompt buffer

#### Scenario: File mention suggestions are visible
- **WHEN** a user types an `@` file mention fragment
- **THEN** the TUI SHALL show matching project paths in a selectable Textual
  suggestion surface
- **AND** accepting a candidate SHALL insert only the selected file mention into
  the prompt buffer

#### Scenario: User attaches images
- **WHEN** a user attaches one or more images in the Textual composer
- **THEN** the TUI SHALL show those attachments as composer state outside the
  editable text buffer
- **AND** submitting the prompt SHALL pass the selected attachments to the model
  turn with the user-authored text
- **AND** deleting prompt text SHALL NOT be required to remove attachment state

#### Scenario: User removes an image attachment
- **WHEN** a user removes an image attachment from the Textual composer
- **THEN** the attachment SHALL be removed from the pending prompt payload
- **AND** the user-authored text SHALL remain unchanged except for explicit user
  edits

### Requirement: Textual Input Reliability Gate
The redesigned Textual composer SHALL pass focused input reliability checks
before it can be considered eligible for a future default-entrypoint change.

#### Scenario: CJK text is entered
- **WHEN** a user enters CJK text in the Textual composer
- **THEN** the visible text, prompt buffer, cursor movement, deletion, and line
  wrapping SHALL remain coherent
- **AND** terminal keyboard-protocol sequences SHALL NOT be visible to the user
  as replacement text

#### Scenario: Wide and composed characters are entered
- **WHEN** a user enters emoji, wide characters, or composed Unicode text
- **THEN** cursor movement and deletion SHALL NOT corrupt adjacent text
- **AND** submitted prompt text SHALL preserve the user's characters

#### Scenario: User inserts newline
- **WHEN** a user presses Ctrl+J in the Textual composer
- **THEN** the composer SHALL insert a newline
- **AND** it SHALL NOT submit the prompt

#### Scenario: User submits prompt
- **WHEN** a user presses Enter while the composer contains prompt text or
  attachments
- **THEN** the composer SHALL submit the current prompt payload
- **AND** it SHALL clear prompt-local draft state after successful submission

#### Scenario: Defensive terminal normalization runs
- **WHEN** terminal-specific encoded text reaches the Textual input boundary
- **THEN** Deepy MAY normalize it before it becomes visible prompt text
- **AND** the normalizer SHALL be covered by focused regression tests
- **AND** normalizer behavior SHALL NOT be used to implement ordinary prompt
  editing semantics

### Requirement: Shared Textual Command Metadata
The redesigned Textual TUI SHALL derive command discovery, help, and slash
suggestions from shared Deepy command metadata instead of maintaining a separate
Textual-only command list.

#### Scenario: User opens help
- **WHEN** a user opens Textual help
- **THEN** commands SHALL be grouped and described from shared command metadata
- **AND** the command set SHALL match the commands supported by the Textual
  surface

#### Scenario: User types slash prefix
- **WHEN** a user types a slash command prefix in the Textual composer
- **THEN** ranking and labels SHALL come from shared command metadata
- **AND** Textual-only affordances SHALL be added through metadata or adapter
  fields rather than a separate parallel registry

#### Scenario: Command is not available in Textual
- **WHEN** a command is known to Deepy but unsupported in the redesigned Textual
  surface
- **THEN** the TUI SHALL hide it or show an explicit unsupported state
- **AND** it SHALL NOT route the command text to the model as a normal prompt

### Requirement: Hermes-Inspired Extension Points
The redesigned Textual TUI SHALL provide architecture seams that can support
selected Hermes-inspired UX features without introducing Hermes runtime
dependencies.

#### Scenario: Busy prompt behavior is extended
- **WHEN** a future change adds queue, steer, or interrupt modes while a model
  turn is running
- **THEN** the Textual composer architecture SHALL have a distinct place for
  busy input policy separate from transcript rendering and command metadata

#### Scenario: Prompt editing is extended
- **WHEN** a future change adds external editor draft editing
- **THEN** the Textual composer architecture SHALL allow the draft to be replaced
  from an editor result without affecting attachments, suggestions, or
  transcript state

#### Scenario: Tool detail behavior is extended
- **WHEN** a future change adds global or per-section detail visibility modes
- **THEN** transcript block state SHALL allow hidden, collapsed, and expanded
  detail rendering without changing runner event shapes
