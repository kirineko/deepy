## ADDED Requirements

### Requirement: Experimental Textual TUI Entry
Deepy SHALL provide an opt-in experimental Textual terminal UI that is launched
only through the dedicated TUI command path.

#### Scenario: User starts the experimental TUI
- **WHEN** a user runs `deepy tui`
- **THEN** Deepy SHALL start a Textual-powered full-screen terminal UI
- **AND** the UI SHALL identify itself as experimental during startup or help
- **AND** the existing default `deepy` interactive UI SHALL NOT be replaced

#### Scenario: User exits the experimental TUI
- **WHEN** a user chooses the TUI exit action
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL return control to the user's terminal without requiring a
  second cleanup command

### Requirement: Textual App Shell
The experimental TUI SHALL use a Deepy-owned Textual app shell for layout,
navigation, live state, and command discovery.

#### Scenario: TUI starts in a project
- **WHEN** the experimental TUI starts
- **THEN** it SHALL show the Deepy identity, current project root, active model,
  reasoning mode, session state, and experimental status
- **AND** it SHALL provide discoverable keyboard help for core actions

#### Scenario: Terminal width changes
- **WHEN** the terminal is resized
- **THEN** the TUI SHALL adapt transcript, prompt, footer, and detail panels to
  the available width
- **AND** text SHALL remain readable without incoherent overlap

#### Scenario: Theme is resolved
- **WHEN** the TUI starts with a saved `auto`, `dark`, or `light` UI theme
- **THEN** it SHALL resolve a Textual theme compatible with that setting
- **AND** transcript text, tool blocks, prompts, status, and diffs SHALL remain
  readable

### Requirement: Textual Prompt Input
The experimental TUI SHALL provide Textual-native prompt input that preserves
Deepy's core input model.

#### Scenario: User submits prompt
- **WHEN** a user enters text and presses Enter
- **THEN** the TUI SHALL submit the prompt to the active Deepy session
- **AND** it SHALL add the submitted prompt to the transcript

#### Scenario: User inserts newline
- **WHEN** a user presses Shift+Enter while editing the prompt
- **THEN** the TUI SHALL insert a newline into the prompt
- **AND** it SHALL NOT submit the prompt

#### Scenario: User opens slash command discovery
- **WHEN** a user types `/` at the beginning of the prompt
- **THEN** the TUI SHALL expose available Deepy slash commands in a selectable
  Textual surface

#### Scenario: User references project files
- **WHEN** a user starts a file mention with `@`
- **THEN** the TUI SHALL provide a project-file mention affordance
- **AND** selected file mentions SHALL be inserted into the prompt text

### Requirement: Live Runner Integration
The experimental TUI SHALL consume Deepy's existing stream-event boundary
instead of depending directly on provider-specific event shapes.

#### Scenario: Model turn streams events
- **WHEN** `run_prompt_once()` emits normalized `DeepyStreamEvent` values
- **THEN** the TUI SHALL update the transcript and live status from those events
- **AND** provider-specific raw event objects SHALL NOT be required by TUI
  widgets

#### Scenario: Model turn is running
- **WHEN** a model turn is in progress
- **THEN** the TUI SHALL show live progress in the Textual app shell
- **AND** the prompt SHALL indicate that the app is busy
- **AND** the UI SHALL remain responsive to supported navigation and interrupt
  actions

#### Scenario: Model turn completes
- **WHEN** the model turn completes
- **THEN** the TUI SHALL show the final assistant output in the transcript
- **AND** it SHALL update session and usage state shown by the app

### Requirement: Navigable Transcript Blocks
The experimental TUI SHALL represent conversation content as navigable,
focusable transcript blocks.

#### Scenario: Transcript contains mixed content
- **WHEN** the session contains user prompts, assistant output, thinking, tool
  calls, tool output, diffs, shell output, todos, questions, errors, or usage
  summaries
- **THEN** the TUI SHALL render each content type with a distinct readable block
- **AND** users SHALL be able to move focus between transcript blocks

#### Scenario: User expands a detail block
- **WHEN** a transcript block has hidden details
- **THEN** the TUI SHALL provide an expand and collapse action
- **AND** expanding the block SHALL reveal details without losing transcript
  position

#### Scenario: Assistant output contains Markdown
- **WHEN** assistant output contains Markdown
- **THEN** the TUI SHALL render it with Textual Markdown-compatible formatting
- **AND** code fences, tables, lists, headings, and inline emphasis SHALL remain
  readable in the transcript

### Requirement: Experimental Tool And Diff Surfaces
The experimental TUI SHALL provide richer Textual surfaces for tool activity and
file diffs without using AGPL code or requiring AGPL dependencies.

#### Scenario: Tool call starts
- **WHEN** Deepy emits a tool call event
- **THEN** the TUI SHALL show a live tool block with the tool label and concise
  parameters

#### Scenario: Tool output arrives
- **WHEN** Deepy emits tool output
- **THEN** the TUI SHALL update the corresponding tool block with success,
  failure, waiting-for-user, or detail state

#### Scenario: Write or modify output contains diff metadata
- **WHEN** a write or modify tool output contains diff metadata
- **THEN** the TUI SHALL render a Deepy-owned diff view
- **AND** the diff view SHALL show file path, added and removed lines, and
  changed content with readable gutters and colors

#### Scenario: Diff view is inspired by references
- **WHEN** implementing the diff view
- **THEN** Deepy SHALL NOT copy toad or textual-diff-view source code
- **AND** Deepy SHALL NOT add toad or textual-diff-view as runtime dependencies
  unless a future license decision explicitly permits it

### Requirement: Experimental Visual Experience
The experimental TUI SHALL use Textual-specific interaction and visual affordances
to make the opt-in experience meaningfully different from the legacy UI.

#### Scenario: UI is idle
- **WHEN** the TUI is waiting for user input
- **THEN** it SHALL show a polished prompt area, status/footer information, and
  discoverable command hints
- **AND** it SHALL avoid unnecessary visual noise that reduces transcript
  readability

#### Scenario: UI is busy
- **WHEN** the TUI is waiting for a model turn or command result
- **THEN** it SHALL show live progress through Textual widgets or subtle
  animation
- **AND** the animation SHALL NOT obscure user prompts, assistant output, or tool
  details

#### Scenario: User needs auxiliary views
- **WHEN** a user opens sessions, skills, status, settings, or help from the TUI
- **THEN** the TUI SHALL present the view as a Textual screen, modal, panel, or
  focusable region
- **AND** closing the view SHALL return the user to the conversation context

### Requirement: Compatibility And Fallback Boundaries
The experimental TUI SHALL keep Deepy's supported runtime and stable UI path
intact.

#### Scenario: Project installs Deepy with Python 3.12
- **WHEN** Deepy is installed in a Python 3.12-compatible environment
- **THEN** the experimental TUI dependencies SHALL remain installable
- **AND** Deepy SHALL NOT require Python 3.14

#### Scenario: User runs default interactive command
- **WHEN** a user runs `deepy` without the `tui` subcommand
- **THEN** Deepy SHALL use the existing Rich and prompt-toolkit interactive UI
- **AND** experimental TUI behavior SHALL NOT change the default UI contract

#### Scenario: Experimental TUI cannot start
- **WHEN** the experimental TUI fails during startup because of terminal or
  dependency limitations
- **THEN** Deepy SHALL show a concise actionable error
- **AND** the user SHALL still be able to run the default `deepy` UI

### Requirement: Textual TUI Testability
The experimental TUI SHALL be testable through Textual-compatible headless tests
and existing Deepy unit boundaries.

#### Scenario: TUI widgets are tested
- **WHEN** tests run for the experimental TUI
- **THEN** they SHALL exercise startup, prompt input, stream-event rendering,
  tool block updates, diff rendering, question selection, navigation, and exit
  behavior through Textual-compatible test helpers

#### Scenario: Legacy UI regression tests run
- **WHEN** tests run after adding the experimental TUI
- **THEN** existing terminal UI tests for the default Rich and prompt-toolkit UI
  SHALL continue to pass
