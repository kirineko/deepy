## ADDED Requirements

### Requirement: Global Interactive UI Owner

Deepy SHALL use a single prompt-toolkit-owned interactive UI owner for idle
input and active model or local-command runtime display.

#### Scenario: Model turn runtime starts
- **WHEN** Deepy starts a model turn from interactive mode
- **THEN** Deepy SHALL attach a running view to the global interactive UI owner
- **AND** the running view SHALL render runtime status, thinking/progress
  summaries, input state, and the compact footer through that owner
- **AND** Deepy SHALL NOT concurrently print active runtime status through a
  separate Rich live/status surface or ANSI terminal-bottom renderer

#### Scenario: Local command runtime starts
- **WHEN** Deepy starts an interactive local command submitted with `!`
- **THEN** Deepy SHALL attach a running view to the global interactive UI owner
- **AND** the running view SHALL render command text, elapsed time, interrupt
  hint, command status, and the compact footer through that owner
- **AND** Deepy SHALL NOT use a separate terminal-bottom renderer for the local
  command runtime lifecycle

#### Scenario: Runtime finishes
- **WHEN** model or local-command runtime work finishes
- **THEN** Deepy SHALL detach the running view
- **AND** Deepy SHALL restore a usable idle prompt for the next user input
- **AND** the next submitted prompt SHALL be accepted without requiring a
  terminal reset or process restart

### Requirement: Event-Driven Runtime View Model

Deepy SHALL convert runtime stream events into view state before rendering active
runtime UI.

#### Scenario: Thinking delta is received
- **WHEN** Deepy receives a thinking delta during a running model turn
- **THEN** Deepy SHALL update the runtime view state with that thinking text
- **AND** the active UI owner SHALL render the updated state
- **AND** the thinking text SHALL NOT be printed directly to normal scrollback
  while the running view is active

#### Scenario: Tool call or tool output is received
- **WHEN** Deepy receives a tool call or tool output event during a running model
  turn
- **THEN** Deepy SHALL update the runtime view state with the tool progress and
  result information
- **AND** the active UI owner SHALL render the updated tool state
- **AND** the tool update SHALL NOT compete with the active prompt footer for
  terminal placement

#### Scenario: Runtime transcript is committed
- **WHEN** the running view finishes
- **THEN** Deepy SHALL commit a complete transcript representation from the
  runtime view state
- **AND** the committed transcript SHALL preserve user echo, complete thinking,
  tool summaries/output, final assistant output, and usage footer when available

### Requirement: Running Input Routing

Deepy SHALL route user input explicitly while a model turn or local command is
running.

#### Scenario: User interrupts running work
- **WHEN** the user presses Esc or Ctrl-C during running work
- **THEN** Deepy SHALL request interruption of the active work
- **AND** the running view SHALL update to reflect interruption or shutdown

#### Scenario: User types during running work
- **WHEN** the user types ordinary text while a model turn is running
- **THEN** Deepy SHALL either queue that text as a follow-up prompt or ignore it
  with a visible runtime hint
- **AND** Deepy SHALL NOT accidentally submit the text as an idle prompt while
  the current turn is still active

#### Scenario: User submits after runtime finishes
- **WHEN** a model turn or local command finishes and the idle prompt is restored
- **THEN** the user SHALL be able to type and submit a new prompt normally
- **AND** that prompt SHALL be processed exactly once

### Requirement: Runtime UI Regression Coverage

Deepy SHALL include PTY-level regression coverage for active runtime UI
ownership.

#### Scenario: Runtime thinking and second prompt are stable
- **WHEN** a scripted interactive PTY session runs a model turn with thinking
  output and then submits a second prompt
- **THEN** the thinking output SHALL remain visible or be committed in full
- **AND** the second prompt SHALL be accepted and processed normally
- **AND** runtime status SHALL NOT remain duplicated in normal scrollback

#### Scenario: Terminal bottom remains stable
- **WHEN** long input, runtime status, and compact footer are near the terminal
  bottom
- **THEN** prompt-toolkit SHALL remain responsible for active UI layout
- **AND** Deepy SHALL NOT rely on ANSI scroll-region ownership to keep footer or
  status visible

## MODIFIED Requirements

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL preserve complete thinking text through the runtime view
state and final transcript commit.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a working status with elapsed time through the
  global interactive UI owner
- **AND** it SHALL show useful thinking/progress summaries when available
- **AND** the working status SHALL preserve the compact interactive status footer
  instead of replacing it with an unrelated status surface
- **AND** in a TTY, the working status and footer SHALL be rendered by the
  prompt-toolkit-owned runtime view instead of a reserved terminal-bottom ANSI
  renderer
- **AND** the working status footer SHALL NOT include thinking transcript text or
  thinking summaries
- **AND** thinking transcript output SHALL use the same bracketed label family as
  tool activity when committed to transcript output

#### Scenario: Thinking delta is received

- **WHEN** Deepy receives thinking text for a model turn
- **THEN** Deepy SHALL immediately add that thinking text to the runtime view
  state without waiting for a buffer-size threshold
- **AND** it SHALL render a visible `[Thinking]` label or equivalent thinking
  header in the live runtime view or committed transcript
- **AND** it SHALL NOT apply summary truncation to the committed thinking text
- **AND** it SHALL preserve readable line breaks in the committed thinking text
- **AND** it SHALL update the runtime status to a concise `thinking` state at
  most once per continuous thinking block
