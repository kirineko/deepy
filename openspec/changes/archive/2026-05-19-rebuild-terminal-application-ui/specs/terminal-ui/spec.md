## ADDED Requirements

### Requirement: Clean-Slate Terminal Application Ownership

Deepy SHALL own the interactive terminal screen through one prompt-toolkit
Application and SHALL treat existing internal UI modules as replaceable
implementation details.

#### Scenario: Interactive TTY starts
- **WHEN** Deepy starts interactive mode in a TTY
- **THEN** Deepy SHALL create one Application layout that owns transcript,
  runtime output, input editing, completions, modal overlays, and footer
  rendering
- **AND** Deepy SHALL NOT use `PromptSession.bottom_toolbar` as the
  model/context footer
- **AND** Deepy SHALL NOT render footer/status content as ordinary prompt text
  or scrollback
- **AND** Deepy MAY delete or replace old internal UI modules that conflict with
  the Application owner

#### Scenario: Internal compatibility conflicts with the new owner
- **WHEN** an existing UI helper, picker, renderer, or prompt-router API
  requires competing terminal ownership
- **THEN** Deepy SHALL replace or remove that internal API rather than adding a
  compatibility shim
- **AND** public command syntax, session persistence, model routing, tool
  execution, and config semantics SHALL remain stable

### Requirement: Modular UI Component Architecture

Deepy SHALL structure the terminal UI as components backed by a shared
event-driven view model.

#### Scenario: Component renders
- **WHEN** a UI component renders transcript, runtime, input, completion, modal,
  or footer content
- **THEN** it SHALL read state from the shared Application view model
- **AND** it SHALL emit actions/events rather than directly running model turns
  or writing terminal-owned regions

#### Scenario: Component is added or removed
- **WHEN** a UI surface such as footer, completion menu, runtime block view, or
  modal picker is added, removed, or replaced
- **THEN** the change SHALL be local to the component, reducer state, and
  controller effects for that surface
- **AND** unrelated components SHALL NOT need to depend on that component's
  internal rendering details

#### Scenario: Side effect is needed
- **WHEN** a component action requires model streaming, slash-command execution,
  session loading, local-command execution, or shutdown
- **THEN** the Application controller SHALL run the side effect
- **AND** resulting updates SHALL return to the UI as events applied to the
  view model

### Requirement: Fixed One-Row Footer

Deepy SHALL render the model/context/runtime status footer as one fixed bottom
layout row.

#### Scenario: Footer is visible
- **WHEN** the interactive screen is visible
- **THEN** the footer SHALL occupy the terminal's bottom row
- **AND** the footer SHALL span the available terminal width
- **AND** transcript, runtime, input, completion, and modal content SHALL NOT
  overwrite or push below the footer

#### Scenario: Footer content is long
- **WHEN** model, cwd, context, runtime status, or help text exceeds the footer
  width
- **THEN** Deepy SHALL truncate or elide footer content within one row
- **AND** the footer SHALL NOT wrap into a second row
- **AND** the UI SHALL NOT reserve a persistent blank area below the footer

#### Scenario: Runtime status changes
- **WHEN** a turn starts, updates, is interrupted, or finishes
- **THEN** the footer view model SHALL update in place
- **AND** runtime status SHALL NOT be duplicated into normal scrollback as a
  repeated status line

### Requirement: Ordered Runtime Blocks

Deepy SHALL render live model, tool, local-command, assistant, and usage output
as ordered runtime blocks.

#### Scenario: Thinking exceeds one terminal row
- **WHEN** thinking text is longer than one terminal row during a model turn
- **THEN** the live runtime viewport SHALL show the thinking text using normal
  terminal-width wrapping
- **AND** it SHALL preserve explicit newlines from the model
- **AND** it SHALL NOT manually wrap by words in a way that differs from final
  terminal output
- **AND** the input editor, completions, modals, and footer SHALL remain usable

#### Scenario: Tool call occurs between thinking chunks
- **WHEN** thinking text is followed by a tool call or tool output and then more
  thinking text
- **THEN** Deepy SHALL render the first thinking block, tool block, and later
  thinking block as distinct ordered blocks
- **AND** tool labels and summaries SHALL NOT be appended to thinking text
- **AND** later thinking text SHALL remain visible after the tool block

#### Scenario: Runtime finishes
- **WHEN** a model turn finishes
- **THEN** Deepy SHALL commit a readable transcript using the same event order
  as the live runtime viewport
- **AND** complete thinking text SHALL remain available in the committed
  transcript

### Requirement: Completion Menu Ownership

Deepy SHALL render slash-command and file-mention suggestions inside the global
Application layout.

#### Scenario: Slash completion at terminal bottom
- **WHEN** the input editor is near the bottom of the terminal and the user
  types `/`
- **THEN** Deepy SHALL show slash-command suggestions in a visible completion
  region owned by the Application
- **AND** the completion region SHALL NOT overlap or hide the fixed footer row

#### Scenario: File mention completion at terminal bottom
- **WHEN** the input editor is near the bottom of the terminal and the user
  types `@`
- **THEN** Deepy SHALL show file-mention suggestions in a visible completion
  region owned by the Application
- **AND** the completion region SHALL NOT overlap or hide the fixed footer row

### Requirement: Modal Flow Ownership

Deepy SHALL run modal command flows through the global Application without
nesting blocking prompt-toolkit Applications inside the active event loop.

#### Scenario: User opens resume picker
- **WHEN** the user runs `/resume` without an argument
- **THEN** Deepy SHALL show the resume picker through the Application modal
  layer
- **AND** it SHALL NOT call `asyncio.run()` from inside an already running event
  loop
- **AND** it SHALL NOT emit un-awaited coroutine warnings

#### Scenario: User closes modal command
- **WHEN** a modal command picker completes or is canceled
- **THEN** Deepy SHALL return focus to a usable idle prompt
- **AND** the fixed footer and completion behavior SHALL remain intact

### Requirement: Application Regression Coverage

Deepy SHALL include PTY-level and unit coverage for the rebuilt Application UI.

#### Scenario: Reported UI failures are covered
- **WHEN** the terminal UI test suite runs
- **THEN** it SHALL cover startup footer placement, no blank gap below footer,
  `/resume`, long thinking wrapping and scrolling, thinking-tool-thinking
  ordering, slash completion at the bottom, file mention completion at the
  bottom, local commands, interruption, and clean `/exit`

#### Scenario: Process exits cleanly
- **WHEN** a scripted PTY session submits `/exit`
- **THEN** the Deepy process SHALL exit without requiring terminal reset,
  additional Enter input, or external termination

## MODIFIED Requirements

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL preserve complete thinking text through ordered live
runtime blocks and final transcript commit.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show working status with elapsed time through the fixed
  Application footer
- **AND** it SHALL show useful thinking/progress content in ordered runtime
  blocks when available
- **AND** the working footer SHALL NOT include thinking transcript text
- **AND** thinking transcript output SHALL use the same bracketed label family
  as tool activity

#### Scenario: Thinking delta is received

- **WHEN** Deepy receives thinking text for a model turn
- **THEN** Deepy SHALL immediately add that thinking text to an ordered runtime
  block without waiting for a buffer-size threshold
- **AND** it SHALL render a visible `[Thinking]` label for the thinking block
- **AND** it SHALL NOT apply summary truncation to the committed thinking text
- **AND** it SHALL preserve readable line breaks in the committed thinking text
- **AND** live thinking text SHALL wrap naturally at terminal width rather than
  being manually word-wrapped or flattened into one prompt line

### Requirement: Resume Experience

Deepy SHALL make session resume understandable before and after selection and
SHALL run the resume picker safely under the global Application UI owner.

#### Scenario: User resumes a session

- **WHEN** a user opens `/resume`
- **THEN** Deepy SHALL show previous sessions with first prompt, status, and
  time
- **AND** the picker SHALL support keyboard selection and Esc cancellation
- **AND** selected history SHALL be visible after resume
- **AND** the picker SHALL NOT crash because of nested `asyncio.run()` or
  un-awaited session-loading coroutines
