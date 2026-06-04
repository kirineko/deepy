## ADDED Requirements

### Requirement: Interactive View Mode Command
Deepy SHALL provide an interactive `/view` command for selecting whether live reasoning transcript text is hidden or shown.

#### Scenario: User toggles view mode with shorthand
- **WHEN** a user runs `/view` without arguments
- **THEN** Deepy SHALL switch between `concise` and `full`
- **AND** it SHALL persist the new view mode to TOML
- **AND** it SHALL print a concise confirmation that includes the new view mode and whether reasoning is hidden or shown
- **AND** it SHALL NOT start a model turn

#### Scenario: User toggles view mode
- **WHEN** a user runs `/view toggle`
- **THEN** Deepy SHALL switch between `concise` and `full`
- **AND** it SHALL persist the new view mode to TOML
- **AND** it SHALL print a concise confirmation that includes the new view mode and whether reasoning is hidden or shown
- **AND** subsequent turns in the same interactive process SHALL use the updated view mode

#### Scenario: User sets concise view mode
- **WHEN** a user runs `/view concise`
- **THEN** Deepy SHALL persist view mode `concise`
- **AND** it SHALL print a concise confirmation that reasoning is hidden
- **AND** subsequent turns in the same interactive process SHALL hide live reasoning transcript text

#### Scenario: User sets full view mode
- **WHEN** a user runs `/view full`
- **THEN** Deepy SHALL persist view mode `full`
- **AND** it SHALL print a concise confirmation that reasoning is shown
- **AND** subsequent turns in the same interactive process SHALL show live reasoning transcript text

#### Scenario: User provides invalid view arguments
- **WHEN** a user runs `/view` with an argument other than `toggle`, `concise`, or `full`
- **THEN** Deepy SHALL reject the command with a concise usage message
- **AND** it SHALL keep the saved view mode unchanged

### Requirement: View Command Discoverability
Deepy SHALL make the view mode command discoverable in interactive command surfaces.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/view` SHALL be included as a built-in command
- **AND** it SHALL be described as a UI display command rather than model thinking configuration

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/view [toggle|concise|full]` in the command list
- **AND** it SHALL describe that the command hides or shows reasoning transcript text

## MODIFIED Requirements

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL render thinking text according to the active UI view mode
when it is received.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a one-line runtime working status with elapsed time
- **AND** it SHALL show useful concise progress state when available
- **AND** when streamed reasoning, assistant output text, or streamed tool-call argument text has been received in the current model turn, the working status SHALL include a current-turn cumulative stream token estimate formatted as `↓ N tokens`
- **AND** token estimates of at least 1000 SHALL use compact `K` suffix formatting such as `↓ 1.1K tokens`
- **AND** this `K`-only formatting SHALL apply only to the runtime stream token estimate, not to the context-window `ctx` segment
- **AND** the current-turn stream token estimate SHALL continue accumulating across streamed reasoning, assistant output, and streamed tool-call argument deltas in the same model turn
- **AND** high-frequency stream deltas SHALL NOT repaint the inline runtime status more often than needed for smooth terminal rendering
- **AND** the current-turn stream token estimate SHALL reset at the start of each model turn
- **AND** the current-turn stream token estimate SHALL remain separate from final provider usage accounting
- **AND** the working status visible text SHALL remain otherwise unchanged from the
  existing runtime status wording
- **AND** the working status SHALL render in the normal output flow rather than
  as a fixed terminal-bottom overlay
- **AND** the working status SHALL be cleared or superseded when normal
  transcript output or the completed model turn takes over
- **AND** the working status SHALL NOT set a terminal scroll region
- **AND** the working status SHALL NOT reserve or write to a fixed
  terminal-bottom row during active work
- **AND** the working status SHALL NOT render the structured prompt footer as a
  second fixed terminal-bottom row
- **AND** normal prompt submissions SHALL NOT perform runtime-status-specific
  bottom-row anchoring after printing submitted user input
- **AND** AskUserQuestion continuation turns SHALL NOT perform
  runtime-status-specific bottom-row anchoring before resumed transcript output
- **AND** runtime-status-specific POSIX or Windows cursor-row probing SHALL NOT
  be required to place resumed output
- **AND** the working status SHALL use segment-level foreground styling to
  distinguish semantic parts such as spinner, elapsed time, interrupt hint,
  detail label, and payload
- **AND** the working status SHALL NOT use a full-line background color
- **AND** the working status SHALL NOT include thinking transcript text
- **AND** thinking transcript output SHALL use the same bracketed label family as
  tool activity when it is shown

#### Scenario: Local command is running

- **WHEN** a local `!cmd` command is in progress
- **THEN** Deepy SHALL show a one-line running status with elapsed time and the
  command being executed
- **AND** the running status visible text SHALL remain unchanged from the
  existing runtime status wording
- **AND** the running status SHALL render in the normal output flow rather than
  as a fixed terminal-bottom overlay
- **AND** the running status SHALL be cleared or superseded when the local
  command completes
- **AND** the running status SHALL NOT set a terminal scroll region
- **AND** the running status SHALL NOT reserve or write to a fixed
  terminal-bottom row during active work
- **AND** the running status SHALL NOT render the structured prompt footer as a
  second fixed terminal-bottom row
- **AND** submitted local-command input SHALL NOT perform
  runtime-status-specific bottom-row anchoring before command output
- **AND** runtime-status-specific POSIX or Windows cursor-row probing SHALL NOT
  be required to place command output
- **AND** the running status SHALL use segment-level foreground styling to
  distinguish semantic parts such as spinner, elapsed time, interrupt hint,
  `local command`, and command payload
- **AND** the running status SHALL NOT use a full-line background color

#### Scenario: Thinking delta is received in concise view

- **WHEN** Deepy receives thinking text for a model turn
- **AND** the active UI view mode is `concise`
- **THEN** Deepy SHALL NOT print the thinking text to normal transcript output
- **AND** it SHALL NOT print a visible `[Thinking]` label for the hidden thinking block
- **AND** it SHALL update the runtime status stream token estimate using the received thinking text
- **AND** it SHALL preserve the reasoning data in the session and stream-event flow where Deepy normally persists it
- **AND** it SHALL NOT change provider reasoning behavior

#### Scenario: Thinking delta is received in full view

- **WHEN** Deepy receives thinking text for a model turn
- **AND** the active UI view mode is `full`
- **THEN** Deepy SHALL immediately stream that thinking text to normal transcript output without waiting for a buffer-size threshold
- **AND** it SHALL print a visible `[Thinking]` label for the thinking block
- **AND** it SHALL NOT apply summary truncation to the thinking text
- **AND** it SHALL preserve readable line breaks in the printed thinking text
- **AND** it SHALL update the runtime status stream token estimate using the received thinking text
