## MODIFIED Requirements

### Requirement: Persistent Interactive Status Footer
Deepy SHALL keep a compact interactive status footer fixed at the terminal
bottom during interactive prompt input and model or local-command work.

#### Scenario: Idle prompt is shown

- **WHEN** Deepy prompts for interactive user input
- **THEN** the prompt bottom footer SHALL show compact status segments for the
  active model and reasoning mode, CWD, and context window status
- **AND** the model and reasoning mode SHALL be represented as a single leading
  segment such as `model deepseek-v4-pro[max]`
- **AND** the footer SHALL NOT show a separate `thinking` label segment for
  reasoning mode
- **AND** the footer SHALL NOT show persistent `Ctrl+D twice exit` help
- **AND** the footer SHALL show the newline hint `newline: ctrl+j`

#### Scenario: Model turn is running

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL reserve the bottom two terminal lines when the output
  stream is a TTY
- **AND** the last line SHALL keep the same compact status footer content and
  background style as the idle prompt footer
- **AND** the line above it SHALL show the realtime running status
- **AND** normal transcript output SHALL scroll above both reserved lines
- **AND** the realtime running status SHALL include working elapsed time, Esc
  interrupt guidance, and active work state
- **AND** the realtime running status SHALL include an animated spinner before
  the elapsed time while work is active
- **AND** the compact footer SHALL include model/reasoning, CWD, MCP status, and
  context window status
- **AND** the footer SHALL NOT be emitted as an ordinary transcript or
  scrollback status line
- **AND** the active work state SHALL use concise state labels such as
  `thinking` instead of reasoning transcript text or generated thinking
  summaries
- **AND** the footer SHALL NOT refresh on every thinking text delta
- **AND** spinner animation refreshes SHALL update only the reserved realtime
  status line
- **AND** working elapsed time and Esc interrupt guidance SHALL appear only in
  the reserved realtime status line, not in normal transcript output
- **AND** runtime status refreshes SHALL NOT interleave with transcript, tool
  result, diff, or shell output writes
- **AND** runtime status text SHALL be truncated and padded by terminal display
  cells so CJK and other wide-character tool details do not corrupt the row

#### Scenario: Local command is running

- **WHEN** Deepy runs an interactive local command submitted with `!`
- **THEN** Deepy SHALL reserve the bottom two terminal lines when the output
  stream is a TTY
- **AND** the last line SHALL keep the same compact status footer content and
  background style as the idle prompt footer
- **AND** the line above it SHALL show the realtime local-command status
- **AND** normal command output SHALL scroll above both reserved lines
- **AND** the realtime local-command status SHALL include working elapsed time,
  Esc interrupt guidance, local command running state, and the command text
- **AND** the realtime local-command status SHALL include an animated spinner
  before the elapsed time while the command is active
- **AND** the compact footer SHALL include CWD, MCP status, and context window
  status
- **AND** the footer SHALL NOT be emitted as an ordinary transcript or
  scrollback status line
- **AND** local-command runtime status refreshes SHALL NOT interleave with
  command output writes
- **AND** local-command runtime status text SHALL be truncated and padded by
  terminal display cells

## ADDED Requirements

### Requirement: Stable Runtime Status Row Fitting
Deepy's stable terminal runtime status row SHALL remain a single clean terminal
row during long-running tool activity.

#### Scenario: WebSearch status contains wide characters
- **WHEN** a stable model turn is running
- **AND** the active tool detail includes WebSearch text with CJK or other
  wide-character content
- **THEN** Deepy SHALL fit the realtime status text to the reserved terminal row
  using display-cell width
- **AND** spinner, elapsed time, interrupt hint, and tool detail SHALL remain on
  one row
- **AND** stale characters from a previous longer status update SHALL NOT remain
  visible after a shorter refresh

#### Scenario: Tool detail exceeds terminal width
- **WHEN** the active stable runtime status detail is longer than the available
  terminal row
- **THEN** Deepy SHALL truncate the detail with an ellipsis or equivalent
  one-row marker
- **AND** it SHALL preserve the spinner, elapsed time, and interrupt hint
- **AND** it SHALL NOT wrap the runtime status into transcript output

#### Scenario: Tool output arrives during spinner refresh
- **WHEN** a tool output event is printed while the stable runtime status
  spinner is refreshing
- **THEN** Deepy SHALL serialize terminal writes so ANSI cursor movement and
  transcript output do not interleave
- **AND** the runtime status row SHALL remain clearable when the turn completes
