# Terminal UI Specification

## Purpose

Deepy uses a Rich and prompt-toolkit terminal interface that makes user input,
assistant output, thinking, tool calls, diffs, usage, and context status readable.
## Requirements
### Requirement: Prompt Input Behavior

Deepy SHALL provide ergonomic multiline terminal input.

#### Scenario: User submits input

- **WHEN** a user presses Enter
- **THEN** Deepy SHALL submit the current prompt

#### Scenario: User inserts a newline

- **WHEN** a user presses Ctrl+J
- **THEN** Deepy SHALL insert a newline into the prompt
- **AND** it SHALL NOT submit the prompt

#### Scenario: User exits with Ctrl+D

- **WHEN** a user presses Ctrl+D once
- **THEN** Deepy SHALL ask for a second Ctrl+D confirmation
- **WHEN** the user presses Ctrl+D again
- **THEN** Deepy SHALL exit cleanly

### Requirement: Markdown Rendering
Deepy SHALL render assistant Markdown as formatted terminal output.

#### Scenario: Assistant returns Markdown

- **WHEN** assistant output contains headings, lists, code blocks, links, or
  inline emphasis
- **THEN** Deepy SHALL render it through the Markdown UI path instead of printing
  raw Markdown syntax
- **AND** fenced code blocks SHALL render as visually distinct terminal code
  blocks rather than visible raw fence markers or plain paragraph text
- **AND** fenced code blocks with a recognized language tag SHOULD include
  syntax-highlighted token styling

### Requirement: Theme-Aware Rendering

Deepy SHALL render terminal UI using a selected theme palette so content remains
readable in both light-background and dark-background terminals.

#### Scenario: User uses a light-background terminal

- **WHEN** the active UI theme resolves to `light`
- **THEN** Deepy SHALL render welcome text, panels, user messages, assistant
  messages, muted status text, thinking/progress summaries, tool panels, and
  diff/write previews with colors that remain legible on a light background

#### Scenario: User uses a dark-background terminal

- **WHEN** the active UI theme resolves to `dark`
- **THEN** Deepy SHALL render welcome text, panels, user messages, assistant
  messages, muted status text, thinking/progress summaries, tool panels, and
  diff/write previews with colors that remain legible on a dark background

#### Scenario: Legacy automatic theme is loaded

- **WHEN** the saved UI theme is the legacy value `auto`
- **THEN** Deepy SHALL treat it as a configured dark-compatible theme
- **AND** it SHALL NOT present `auto` as a selectable theme to the user

#### Scenario: User changes theme inside an interactive session

- **WHEN** a user runs `/theme light` or `/theme dark`
- **THEN** Deepy SHALL persist the selected theme
- **AND** subsequent interactive output SHALL use the selected theme
- **AND** it SHALL advise the user to restart Deepy so the theme applies
  everywhere

#### Scenario: User chooses theme inside an interactive session

- **WHEN** a user runs `/theme` without an argument
- **THEN** Deepy SHALL show the current saved theme once
- **AND** it SHALL show keyboard-selectable `dark` and `light` theme choices
- **AND** fallback non-picker flows SHALL accept a selected theme by number or
  name
- **AND** it SHALL advise the user to restart Deepy after persisting the
  selected theme

#### Scenario: User provides an invalid interactive theme

- **WHEN** a user runs `/theme` with a value other than `dark` or `light`
- **THEN** Deepy SHALL reject the value with a concise usage message
- **AND** it SHALL keep the previously saved theme

#### Scenario: User resets configuration inside an interactive session

- **WHEN** a user runs `/reset`
- **THEN** Deepy SHALL delete the existing TOML config file when it exists
- **AND** it SHALL guide the user through interactive setup again
- **AND** subsequent interactive output SHALL use the newly saved UI theme

### Requirement: Thinking And Progress Display

Deepy SHALL show model work progress without requiring realtime final-answer
streaming, and SHALL render thinking text according to the active UI view mode
when it is received.

#### Scenario: Model is working

- **WHEN** a model turn is in progress
- **THEN** Deepy SHALL show a one-line runtime working status with elapsed time
- **AND** it SHALL show the current-turn cumulative stream token estimate when
  available
- **AND** it SHALL show a concise current activity state before the interrupt
  hint, such as `Thinking`, `Write`, `WebFetch`, or `MCP`
- **AND** tool activity state SHALL show only the tool display name and SHALL
  NOT include tool arguments or parameter payloads
- **AND** the visible order SHALL be elapsed time, token estimate when present,
  current activity state when present, and `esc to interrupt`
- **AND** high-frequency stream deltas SHALL NOT repaint the inline runtime
  status more often than needed for smooth terminal rendering

### Requirement: Resume Experience

Deepy SHALL make session resume understandable before and after selection.

#### Scenario: User resumes a session

- **WHEN** a user opens `/resume`
- **THEN** Deepy SHALL show previous sessions with first prompt, status, and time
- **AND** the picker SHALL support keyboard selection and Esc cancellation
- **AND** selected history SHALL be visible after resume

### Requirement: Startup Screen
Deepy SHALL show a compact welcome panel.

#### Scenario: User starts interactive mode

- **WHEN** Deepy starts
- **THEN** the welcome panel SHALL show the Deepy identity, version, provider,
  model, thinking settings, CWD, active UI theme, and only core commands
- **AND** the welcome panel SHALL prefer a wide layout with enough vertical
  spacing for readable grouped content when terminal width allows
- **AND** the welcome panel SHALL include a compact Deepy logo or equivalent
  identity mark
- **AND** the welcome panel SHALL show a concise product description near the
  Deepy identity
- **AND** the welcome panel SHALL avoid duplicating startup information across
  multiple large vertical sections
- **AND** the welcome panel SHALL group startup metadata under a `Session`
  heading
- **AND** the welcome panel SHALL group common commands under a `Commands`
  heading
- **AND** core command entries SHALL render one command per line in a consistent
  label-and-description style

#### Scenario: First interactive startup has no saved theme

- **WHEN** Deepy starts interactive mode and no valid UI theme is saved
- **THEN** Deepy SHALL show numbered `dark` and `light` theme choices
- **AND** it SHALL allow theme selection by number while accepting theme names as
  a fallback
- **AND** it SHALL persist the choice before rendering the welcome panel
- **AND** the welcome panel SHALL use the selected theme

### Requirement: Fast Startup Readiness

Deepy SHALL render the stable terminal UI welcome screen and prompt without
waiting for startup network checks or MCP connection to complete.

#### Scenario: Welcome renders before version check completes

- **WHEN** Deepy starts the stable terminal UI
- **AND** the startup version check has not completed
- **THEN** Deepy SHALL render the welcome screen without waiting for the version
  check result
- **AND** Deepy SHALL show concise pending update state in the startup UI or
  prompt footer

#### Scenario: Welcome renders before MCP connection completes

- **WHEN** Deepy starts the stable terminal UI
- **AND** configured MCP servers have not completed connection
- **THEN** Deepy SHALL render the welcome screen without waiting for MCP
  connection
- **AND** Deepy SHALL show concise pending MCP state in the prompt footer

#### Scenario: Prompt is available during startup background work

- **WHEN** the welcome screen has rendered
- **AND** startup version or MCP work is still pending
- **THEN** Deepy SHALL allow the user to enter prompt input
- **AND** prompt input SHALL remain visually coherent while startup state changes

#### Scenario: MCP completes after prompt is visible

- **WHEN** MCP connection completes after the prompt is visible
- **THEN** Deepy SHALL refresh the prompt footer state from pending MCP state to
  connected MCP count when active servers are available
- **AND** Deepy SHALL NOT print raw background output that corrupts the prompt
  input row

#### Scenario: Update is found before prompt starts

- **WHEN** the startup version check discovers a newer version before prompt
  input starts
- **THEN** Deepy SHALL include the update state in the welcome information before
  the first prompt is shown

#### Scenario: Update is found after prompt starts

- **WHEN** the startup version check discovers a newer version after prompt input
  has started
- **THEN** Deepy SHALL show one concise prompt-toolkit-safe terminal notification
- **AND** Deepy SHALL NOT redraw the full welcome panel while prompt input owns
  the terminal

#### Scenario: User submits before MCP is ready

- **WHEN** the user submits the first model prompt before MCP connection has
  completed
- **THEN** Deepy SHALL wait for MCP readiness before starting the model turn
- **AND** Deepy SHALL show runtime progress while waiting
- **AND** the model turn SHALL use the configured MCP runtime after it is ready

#### Scenario: MCP startup fails

- **WHEN** MCP connection fails during background startup
- **THEN** Deepy SHALL continue the stable terminal session
- **AND** the first model turn SHALL proceed with the failed MCP state recorded
  in the MCP runtime
- **AND** MCP status inspection SHALL remain available through existing MCP
  status surfaces

#### Scenario: Terminal ownership is preserved

- **WHEN** startup update or MCP state changes while prompt-toolkit is reading
  input
- **THEN** Deepy SHALL update the UI through prompt-toolkit-safe mechanisms
- **AND** Deepy SHALL NOT directly write Rich output from the background startup
  task into the active prompt area

### Requirement: Interactive Model Selection Command
Deepy SHALL provide an interactive `/model` command for selecting the active
provider, model, and provider-appropriate thinking mode with minimal typing.

#### Scenario: User opens model picker
- **WHEN** a user runs `/model` without arguments
- **THEN** Deepy SHALL show the current provider, model, and thinking mode
- **AND** it SHALL present selectable providers `DeepSeek`, `OpenRouter`, and `Xiaomi`
- **AND** `DeepSeek` SHALL be the default provider for new or legacy configurations

#### Scenario: User selects provider then model then thinking mode
- **WHEN** a user selects a provider from the `/model` picker
- **THEN** Deepy SHALL present only models supported by that provider
- **AND** after model selection it SHALL present only thinking choices supported by that provider
- **AND** DeepSeek SHALL offer `none`, `high`, and `max`
- **AND** OpenRouter SHALL offer `enabled`, `disabled`, `xhigh`, `high`,
  `medium`, `low`, `minimal`, and `none`
- **AND** Xiaomi MiMo SHALL offer `disabled` and `enabled`
- **AND** it SHALL save the selected provider, model, and thinking mode only after all selections are complete

#### Scenario: User cancels model selection
- **WHEN** a user cancels the `/model` picker before completing all selections
- **THEN** Deepy SHALL leave the saved model settings unchanged
- **AND** it SHALL keep the current interactive session settings unchanged

#### Scenario: User completes model selection
- **WHEN** a user completes `/model` selection
- **THEN** Deepy SHALL persist the selected provider, model, and thinking settings
- **AND** subsequent turns in the same interactive process SHALL use the updated provider and model settings
- **AND** Deepy SHALL print a concise confirmation with the active provider, model, and thinking mode

### Requirement: Direct Model Command Forms
Deepy SHALL provide direct `/model` command forms for users who prefer explicit
arguments or are using non-picker terminal flows.

#### Scenario: User lists supported models
- **WHEN** a user runs `/model list`
- **THEN** Deepy SHALL list supported models grouped by provider
- **AND** it SHALL show the available thinking choices for each provider family

#### Scenario: User sets DeepSeek model directly
- **WHEN** a user runs `/model set deepseek-v4-pro` or `/model set deepseek-v4-flash`
- **THEN** Deepy SHALL persist provider `deepseek` and the selected model
- **AND** it SHALL keep the current DeepSeek reasoning mode unless a reasoning mode is also selected

#### Scenario: User sets provider and MiMo model directly
- **WHEN** a user runs `/model set openrouter xiaomi/mimo-v2.5-pro high`
- **OR** a user runs `/model set openrouter xiaomi/mimo-v2.5 none`
- **OR** a user runs `/model set xiaomi mimo-v2.5-pro enabled`
- **OR** a user runs `/model set xiaomi mimo-v2.5 disabled`
- **THEN** Deepy SHALL persist the selected provider, model, and provider-appropriate thinking mode

#### Scenario: User sets provider directly
- **WHEN** a user runs `/model provider deepseek`, `/model provider openrouter`, or `/model provider xiaomi`
- **THEN** Deepy SHALL persist the selected provider
- **AND** it SHALL choose that provider's default model and default thinking mode when the current model is not valid for the selected provider

#### Scenario: User sets reasoning mode directly
- **WHEN** a user runs `/model reasoning none`, `/model reasoning high`, or `/model reasoning max`
- **THEN** Deepy SHALL persist the selected DeepSeek reasoning mode
- **AND** it SHALL keep the current provider and model when they support that reasoning mode

#### Scenario: User sets switch-only thinking directly
- **WHEN** a user runs `/model thinking enabled` or `/model thinking disabled`
- **THEN** Deepy SHALL persist the selected switch-only thinking mode when the current provider supports it
- **AND** it SHALL keep the current provider and model

#### Scenario: User provides invalid model command arguments
- **WHEN** a user runs `/model` with unsupported arguments, provider, model, or thinking mode
- **THEN** Deepy SHALL reject the command with a concise usage message
- **AND** it SHALL keep the saved model settings unchanged

### Requirement: Model Selection Discoverability
Deepy SHALL make provider and model selection discoverable in the interactive
terminal UI.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/model` SHALL be included as a built-in command

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/model` in the command list
- **AND** it SHALL describe provider, model, and thinking selection at a high level

#### Scenario: Startup screen is shown
- **WHEN** Deepy starts interactive mode
- **THEN** the welcome panel SHALL show the active provider, model, and thinking mode

### Requirement: Clarification Question Flow

Deepy SHALL render AskUserQuestion prompts as a user-facing terminal interaction and SHALL continue the active interactive turn across repeated clarification rounds.

#### Scenario: First clarification round is requested

- **WHEN** a model turn returns `status="waiting_for_user"` with pending AskUserQuestion questions
- **THEN** Deepy SHALL display the questions and options to the user
- **AND** it SHALL collect the user's answers
- **AND** it SHALL continue the same session using the collected answers

#### Scenario: Follow-up clarification round is requested

- **WHEN** the model asks another AskUserQuestion after receiving answers from a previous AskUserQuestion round
- **THEN** Deepy SHALL display the follow-up questions and options
- **AND** it SHALL collect the user's answers
- **AND** it SHALL continue the same session using the collected answers

#### Scenario: Clarification rounds complete

- **WHEN** a continued model turn completes without `status="waiting_for_user"`
- **THEN** Deepy SHALL render the assistant output and usage footer for the completed turn
- **AND** it SHALL not drop any pending assistant output from the final continuation

#### Scenario: Clarification round limit is reached

- **WHEN** repeated AskUserQuestion rounds exceed Deepy's defensive per-turn limit
- **THEN** Deepy SHALL stop collecting further clarification rounds
- **AND** it SHALL show a concise message indicating that clarification stopped because the round limit was reached

### Requirement: Clarification Prompt Display

Deepy SHALL keep AskUserQuestion interaction readable by hiding internal tool
protocol details from normal terminal output and by presenting custom answers as
an explicit user-facing option.

#### Scenario: AskUserQuestion tool call is streamed

- **WHEN** Deepy renders a streamed AskUserQuestion tool call
- **THEN** the terminal output SHALL NOT include the raw `questions` argument JSON
- **AND** it SHALL show only a concise AskUserQuestion progress label using the
  same display label style as other tools

#### Scenario: AskUserQuestion history is rendered

- **WHEN** Deepy renders session history containing an AskUserQuestion tool call
- **THEN** the history output SHALL NOT include the raw `questions` argument JSON
- **AND** it SHALL preserve a concise indication that AskUserQuestion was used
- **AND** it SHALL use the same display label style as other tools

#### Scenario: Clarification options are displayed

- **WHEN** Deepy displays AskUserQuestion options to the user
- **THEN** it SHALL include a clearly labeled custom-answer option
- **AND** the custom-answer label SHALL be understandable in the question's
  language when the question language is clear
- **AND** the prompt SHALL make clear that selecting or typing the custom-answer
  option allows free-form text

#### Scenario: User answers clarification questions

- **WHEN** Deepy sends formatted AskUserQuestion answers back to the model
- **THEN** the answer message SHALL include the selected or custom answer text
- **AND** it SHALL NOT include internal option sentinel names in normal
  user-facing output

### Requirement: Manual Compact Command

Deepy SHALL expose an interactive `/compact` command for durable context
compaction.

#### Scenario: User compacts active session

- **WHEN** a user runs `/compact` while an active session has compactable history
- **THEN** Deepy SHALL run durable session compaction
- **AND** it SHALL show concise progress while compaction is running
- **AND** it SHALL print a success message with before and after context token
  estimates

#### Scenario: User provides compact focus

- **WHEN** a user runs `/compact <focus>`
- **THEN** Deepy SHALL pass `<focus>` as the manual compaction focus instruction
- **AND** it SHALL keep the current session active after compaction succeeds

#### Scenario: User compacts without active session

- **WHEN** a user runs `/compact` before any session is active
- **THEN** Deepy SHALL show that there is no active session to compact
- **AND** it SHALL NOT start a new session

#### Scenario: Compact command fails

- **WHEN** manual compaction fails
- **THEN** Deepy SHALL show a concise failure message
- **AND** it SHALL keep the current session active and unchanged

### Requirement: Compact Command Discoverability

Deepy SHALL make the compact command discoverable in interactive command
surfaces.

#### Scenario: Slash command completions are built

- **WHEN** Deepy builds slash command completions
- **THEN** `/compact` SHALL be included as a built-in command

#### Scenario: User asks for help

- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/compact [focus]` in the command list

#### Scenario: Startup screen is shown

- **WHEN** Deepy starts interactive mode
- **THEN** the welcome panel SHALL include `/compact` only if the compact command
  is part of the core command set displayed there

### Requirement: Automatic Compact Feedback

Deepy SHALL make automatic compaction visible without overwhelming normal chat
output.

#### Scenario: Auto compaction runs before a turn

- **WHEN** Deepy automatically compacts context before sending a user prompt to
  the model
- **THEN** the terminal UI SHALL show a concise compaction status message
- **AND** the final usage footer SHALL reflect the compacted context estimate

#### Scenario: Auto compaction fails before a turn

- **WHEN** automatic compaction fails before the model request starts
- **THEN** the terminal UI SHALL show the compaction error
- **AND** it SHALL NOT render a misleading assistant response for that prompt

### Requirement: Bottom Context Status Accuracy

Deepy's interactive status footer SHALL show Cline-style Context Window usage without a separate compaction pressure token segment.

#### Scenario: Latest request usage is known

- **WHEN** a model request completes with usable token usage
- **THEN** the footer SHALL show Context Window usage based on the latest request context occupancy
- **AND** it SHALL use a compact `ctx` label for that segment
- **AND** it SHALL show the configured context window as the total
- **AND** it SHALL show the percentage as latest request context occupancy divided by the configured context window
- **AND** it SHALL NOT show a separate `compact` token pressure segment
- **AND** it SHALL NOT use the redundant label `ctx win`

#### Scenario: Latest turn is short

- **WHEN** a session has existing context and the user sends a short follow-up prompt
- **THEN** the footer Context Window usage SHALL reflect the latest request occupancy even when it is lower than the previous request
- **AND** it SHALL NOT show the previous effective session pressure as a second compact value

#### Scenario: Esc-only prompt rollback occurs

- **WHEN** a submitted prompt is interrupted with Esc before the turn persists assistant or tool output
- **AND** the previous session state has known latest request Context Window usage
- **THEN** the prompt footer SHALL continue to show the previous latest request Context Window usage
- **AND** it SHALL NOT show internal active-token estimates as Context Window used tokens

#### Scenario: Context state is near compaction threshold

- **WHEN** latest request Context Window used tokens are at or above the configured compact threshold
- **THEN** the footer SHALL append a concise `compact next` hint to the `ctx` segment
- **AND** it SHALL NOT show a separate compaction pressure token count

#### Scenario: Explicit compaction reduces context

- **WHEN** manual or automatic compaction rewrites the active session
- **THEN** Context Window usage SHALL update to the compacted replacement history checkpoint
- **AND** the footer SHALL NOT show a separate compacted-history pressure value
- **AND** the compaction success message SHALL use the pre-compaction Context Window used value as its before token count when available

### Requirement: Width-Aware Diff Preview Rendering

Deepy SHALL render file change previews with a unified write/edit diff style
whose changed-line backgrounds fill the available terminal width and whose large
`Write` and `Update` previews are bounded by the shared diff preview line limit.

#### Scenario: Successful file mutation with diff preview omits redundant summary
- **WHEN** Deepy renders a successful `Write` or `Update` result that includes a
  diff preview
- **THEN** the stable terminal UI SHALL render the diff header and diff preview
- **AND** it SHALL omit the generic successful tool summary line
- **AND** the diff header SHALL continue to show the tool label, changed file
  path, and added/removed line counts

#### Scenario: Large write preview is truncated
- **WHEN** Deepy renders a `Write` result whose diff preview exceeds the shared
  diff preview line limit
- **THEN** the stable terminal UI SHALL truncate the rendered diff preview
- **AND** it SHALL indicate how many diff lines were truncated

#### Scenario: File mutation without diff preview keeps summary
- **WHEN** Deepy renders a `Write` or `Update` result without a diff preview
- **THEN** the stable terminal UI SHALL keep rendering the tool summary line

#### Scenario: Failed file mutation keeps summary
- **WHEN** Deepy renders a failed or retryable `Write` or `Update` result
- **THEN** the stable terminal UI SHALL keep rendering the tool summary line

### Requirement: Unified Tool Activity Display

Deepy SHALL render tool calls and tool outputs with concise, consistent labels.

#### Scenario: Read tool call parameters use concise paths

- **WHEN** Deepy renders a streamed `Read` tool call with one or more path
  arguments
- **THEN** the first visible tool token SHALL show the normalized `[Read]`
  display label followed by the requested paths
- **AND** paths under the current project root SHALL be displayed relative to
  that project root
- **AND** the parameter text SHALL NOT expose JSON object keys, list brackets,
  or absolute project-root-prefixed paths when path values can be extracted

### Requirement: Unified Write And Edit Preview Headers

Deepy SHALL render file-change preview headers as tool activity rather than as a
separate `Wrote` or `Edited` display style.

#### Scenario: Write preview is rendered

- **WHEN** a successful write result includes a diff preview
- **THEN** Deepy SHALL render the preview header with the same display label
  convention used for tool activity
- **AND** the header SHALL include the changed path when available
- **AND** the header SHALL include added and removed line counts
- **AND** the header SHALL NOT lead with a standalone `Wrote` label

#### Scenario: Modify preview is rendered

- **WHEN** a successful modify or edit result includes a diff preview
- **THEN** Deepy SHALL render the preview header with the same display label
  convention used for tool activity
- **AND** the header SHALL include the changed path when available
- **AND** the header SHALL include added and removed line counts
- **AND** the header SHALL NOT lead with a standalone `Edited` label

### Requirement: Token Usage Display Semantics

Deepy's terminal UI SHALL present Token Usage as cumulative API token consumption rather than as context window occupancy.

#### Scenario: Per-turn usage footer is shown

- **WHEN** a model turn completes with usage data
- **THEN** the usage footer SHALL label the displayed values as Token Usage
- **AND** it SHALL include input, output, cache, reasoning, request count, and total fields when known
- **AND** it SHALL NOT imply that the cumulative total is the current Context Window used value

#### Scenario: Session usage is summarized

- **WHEN** Deepy displays accumulated session usage
- **THEN** it SHALL aggregate usage across recorded model requests
- **AND** it SHALL keep the accumulated Token Usage separate from latest request Context Window usage

### Requirement: Context Window Display Semantics

Deepy's terminal UI SHALL present Context Window as latest request occupancy of the configured context window.

#### Scenario: Context window values are shown

- **WHEN** latest request context usage is known
- **THEN** Deepy SHALL show used tokens, total configured context window tokens, remaining tokens, and percentage
- **AND** the used tokens SHALL be derived from latest request context occupancy

#### Scenario: Context window data is unavailable

- **WHEN** latest request context usage is unavailable
- **THEN** Deepy SHALL show the Context Window value as unknown or estimated
- **AND** it SHALL NOT reuse accumulated Token Usage as a fallback Context Window used value

### Requirement: File Mention Completion
Deepy SHALL provide `@` file and directory mention completion in the
interactive terminal prompt without depending on external system commands.

#### Scenario: User opens top-level file mention completion
- **WHEN** a user types `@` in a prompt position that is not embedded in another
  word
- **THEN** Deepy SHALL show file and directory candidates from the active
  project root
- **AND** directory candidates SHALL include a trailing `/`
- **AND** common generated, dependency, virtual environment, cache, and VCS
  entries SHALL be excluded

#### Scenario: User narrows file mention candidates
- **WHEN** a user continues typing non-whitespace characters after `@`
- **THEN** Deepy SHALL filter candidates by the typed fragment
- **AND** candidates whose basename starts with the typed fragment SHALL rank
  ahead of weaker relative-path fuzzy matches

#### Scenario: Short fragment searches nested project paths
- **WHEN** a user types a short non-empty `@` fragment without a directory
  separator
- **THEN** Deepy SHALL include matching nested files and directories from the
  active project root in the completion candidates
- **AND** the search SHALL remain bounded by the same candidate limit, cache,
  ignore rules, symlink exclusions, and project-root containment rules used by
  file mention discovery
- **AND** basename-prefix matches SHALL rank ahead of weaker relative-path fuzzy
  matches

#### Scenario: Bare at sign remains top-level
- **WHEN** a user types only `@` without a fragment
- **THEN** Deepy SHALL keep showing top-level project candidates
- **AND** it SHALL NOT flood the completion menu with every nested project path

#### Scenario: User descends into a directory
- **WHEN** a user types an `@` fragment containing `/`
- **THEN** Deepy SHALL search from the typed directory scope when that scope is
  within the active project root
- **AND** Deepy SHALL include matching files and directories inside that scope

#### Scenario: User accepts a mention candidate
- **WHEN** a file mention candidate is selected and the user presses Tab
- **THEN** Deepy SHALL replace the current `@` fragment with the selected
  relative path mention
- **AND** the accepted mention SHALL remain editable as plain prompt text

#### Scenario: User completes an existing file mention
- **WHEN** the current `@` fragment already resolves to an existing file under
  the active project root
- **THEN** Deepy SHALL stop offering additional file mention candidates for that
  fragment

#### Scenario: User types an embedded at sign
- **WHEN** a user types an at sign embedded in another token such as an email
  address
- **THEN** Deepy SHALL NOT open file mention completion

#### Scenario: File discovery runs on a machine without search binaries
- **WHEN** the user machine does not provide `rg`, `fd`, `find`, or `git`
- **THEN** Deepy SHALL still provide file mention completion using in-process
  file discovery
- **AND** Deepy SHALL NOT require shelling out to any system search command

#### Scenario: Scoped traversal attempts to escape the project root
- **WHEN** the typed `@` directory scope would resolve outside the active
  project root
- **THEN** Deepy SHALL reject that scope for completion
- **AND** Deepy SHALL NOT include candidates outside the active project root

#### Scenario: Slash command completion remains available
- **WHEN** a user types a slash command token in the interactive prompt
- **THEN** Deepy SHALL continue to offer slash command completions
- **AND** file mention completion SHALL NOT interfere with slash command
  completion

### Requirement: Local Command Mode
Deepy's interactive terminal prompt SHALL execute prompts beginning with `!` as
local shell commands without sending that prompt to the model.

#### Scenario: User runs a local command
- **WHEN** a user submits prompt text whose trimmed value starts with `!`
- **AND** the text after `!` contains a non-empty command
- **THEN** Deepy SHALL execute that command locally instead of sending the
  prompt to the model
- **AND** Deepy SHALL render the command result in the terminal

#### Scenario: User submits an empty local command
- **WHEN** a user submits `!` with no command text after it
- **THEN** Deepy SHALL show a concise usage message
- **AND** it SHALL NOT send a model request
- **AND** it SHALL NOT append a command transcript to the session

#### Scenario: Local command uses the detected shell
- **WHEN** Deepy executes a local command-mode command
- **THEN** it SHALL use the current runtime shell dialect for the user's
  platform, including zsh or bash on POSIX-like systems and PowerShell or cmd on
  Windows

#### Scenario: POSIX local command has a terminal environment
- **WHEN** Deepy executes a local command-mode command on macOS or Linux
- **THEN** it SHALL provide a TTY or PTY-backed execution environment

#### Scenario: Windows local command is non-interactive
- **WHEN** Deepy executes a local command-mode command on Windows
- **THEN** it SHALL execute the command without allocating a pseudo-terminal
- **AND** it SHALL NOT depend on `pywinpty`
- **AND** it SHALL NOT support commands that require interactive stdin, editors,
  pagers, or full-screen terminal UI

#### Scenario: Windows local command preserves the prompt
- **WHEN** Deepy executes a Windows local command-mode command that emits
  terminal control sequences
- **THEN** Deepy SHALL NOT render those control sequences as subsequent prompt
  input
- **AND** the next interactive prompt SHALL accept normal user text

#### Scenario: Windows local command output is normalized
- **WHEN** a Windows local command completes with captured stdout or stderr
- **THEN** Deepy SHALL decode Windows-native command output into readable
  Unicode text before rendering
- **AND** it SHALL normalize Windows line endings to readable line breaks
- **AND** it SHALL remove terminal control sequences from the rendered shell
  output
- **AND** it SHALL preserve printable Unicode text

#### Scenario: Local command exits
- **WHEN** a local command completes
- **THEN** Deepy SHALL render captured terminal output
- **AND** it SHALL render whether the command succeeded or the exit code when it
  failed

#### Scenario: Local command is interrupted or times out
- **WHEN** a local command is interrupted or exceeds the configured timeout
- **THEN** Deepy SHALL terminate the command when possible
- **AND** it SHALL render the partial captured output and interrupted status

#### Scenario: Local command attempts to change directory
- **WHEN** a user runs a local command such as `!cd subdir`
- **THEN** that command SHALL NOT change Deepy's active project root
- **AND** it SHALL NOT change the working directory used for future local
  command-mode commands

#### Scenario: User enters normal prompt text
- **WHEN** a user submits prompt text that does not start with `!` after
  trimming
- **THEN** Deepy SHALL keep the existing model prompt behavior

#### Scenario: Local command output is long
- **WHEN** local command output exceeds the terminal display limit
- **THEN** Deepy SHALL bound the displayed output
- **AND** it SHALL indicate that output was truncated

### Requirement: Skill Management Slash Commands

Deepy SHALL provide `/skills` subcommands and a dedicated full-screen skill
management menu for local skill management and market browsing.

#### Scenario: User opens skill management

- **WHEN** a user runs `/skills` without arguments
- **THEN** Deepy SHALL show local skill management options and the available subcommands

#### Scenario: User lists local skills

- **WHEN** a user runs `/skills list`
- **THEN** Deepy SHALL list discovered project, user, and built-in skills grouped by scope

#### Scenario: User searches market skills

- **WHEN** a user runs `/skills search pdf`
- **THEN** Deepy SHALL show matching market skills or a concise market access error

#### Scenario: User views an installed skill from the menu

- **WHEN** a user selects an installed project, user, or market-managed skill in the `/skills` menu
- **AND** the user invokes the view action
- **THEN** Deepy SHALL show the skill details in a dedicated full-screen viewer
- **AND** it SHALL render Markdown structure from the skill body for readable viewing
- **AND** it SHALL NOT print the skill body into the main Deepy output area

#### Scenario: User views an uninstalled market skill from the menu

- **WHEN** a user selects an uninstalled market skill in the `/skills` menu
- **AND** the user invokes the view action
- **THEN** Deepy SHALL show available market metadata in a dedicated full-screen viewer
- **AND** it SHALL render Markdown structure from market description fields when present
- **AND** it SHALL NOT report that the skill is missing solely because no local install path exists

#### Scenario: User chooses install scope for a market skill

- **WHEN** a user selects an uninstalled market skill in the `/skills` menu
- **AND** the user invokes the install action
- **THEN** Deepy SHALL show a dedicated scope selection window for user or project installation
- **AND** the selected scope SHALL control the install destination

### Requirement: Skill Invocation Slash Completion
Deepy SHALL complete active skill invocation commands when the user types `/skill:`.

#### Scenario: Completion after skill prefix
- **WHEN** the prompt input contains `/skill:`
- **THEN** slash completion SHALL include available skill names as `/skill:<name>` entries

#### Scenario: Skill completion includes descriptions
- **WHEN** Deepy renders completion options for `/skill:`
- **THEN** each skill completion SHALL include the skill description when available

### Requirement: Active Skill Invocation Command
Deepy SHALL treat `/skill:<name> [request]` as an active skill invocation rather than a management command.

#### Scenario: Active skill invocation submits a turn
- **WHEN** a user runs `/skill:review summarize this change`
- **THEN** Deepy SHALL submit a model turn with the `review` skill loaded and the remaining text as the user request

#### Scenario: Unknown active skill
- **WHEN** a user runs `/skill:missing`
- **THEN** Deepy SHALL report that the skill was not found and SHALL NOT submit a model turn

### Requirement: MCP Command Discoverability
Deepy SHALL make MCP status discoverable in interactive command surfaces.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/mcp` SHALL be included as a built-in command

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/mcp` in the command list
- **AND** the description SHALL indicate that it shows MCP server status and
  tools

### Requirement: MCP Status Display
Deepy SHALL provide a concise `/mcp` status view for configured MCP servers.

#### Scenario: User opens MCP status
- **WHEN** a user runs `/mcp`
- **THEN** Deepy SHALL show configured MCP servers with their connection state
- **AND** it SHALL show tool counts for active servers
- **AND** it SHALL show concise failure reasons for failed or invalid servers

#### Scenario: Active MCP tools are available
- **WHEN** a configured MCP server is active and exposes tools
- **THEN** `/mcp` SHALL show model-visible MCP tool names
- **AND** preferred MCP web-search tools SHALL be visually identifiable in the
  status output

#### Scenario: MCP has no configured servers
- **WHEN** a user runs `/mcp` and no MCP servers are configured
- **THEN** Deepy SHALL show a concise message explaining that no MCP servers are
  configured

#### Scenario: MCP status includes secrets
- **WHEN** MCP server configuration contains environment variables, headers, or
  token-like values
- **THEN** `/mcp` SHALL NOT print plaintext secret values

### Requirement: MCP Runtime Status

Deepy SHALL surface MCP availability without overwhelming normal chat output.

#### Scenario: Startup screen is shown

- **WHEN** Deepy starts interactive mode
- **AND** MCP is enabled
- **THEN** the welcome or status surface SHALL show a concise MCP availability
  summary

#### Scenario: Bottom toolbar is shown

- **WHEN** MCP servers are active in an interactive session
- **THEN** the interactive status footer SHALL include the exact compact indicator `mcp N`, where `N` is the number of active MCP servers
- **AND** the indicator SHALL use lowercase `mcp`
- **AND** the indicator SHALL NOT replace context window usage or AGENTS.md
  status information

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

### Requirement: Interactive Status Footer Visual Hierarchy

Deepy SHALL render the interactive status footer with theme-aware visual hierarchy instead of treating all segments as one undifferentiated text style.

#### Scenario: Footer is rendered in a dark theme

- **WHEN** the active UI theme resolves to `dark`
- **THEN** the footer SHALL use one coordinated foreground color family for model identity, active-work state, loaded indicators, and muted metadata
- **AND** separators SHALL use a lower-contrast color from the same theme
- **AND** the footer SHALL NOT render unrelated bright accent color blocks across adjacent segments
- **AND** all footer text SHALL remain readable on the dark toolbar background

#### Scenario: Footer is rendered in a light theme

- **WHEN** the active UI theme resolves to `light`
- **THEN** the footer SHALL use one coordinated foreground color family for model identity, active-work state, loaded indicators, and muted metadata
- **AND** separators SHALL use a lower-contrast color from the same theme
- **AND** the footer SHALL NOT render unrelated bright accent color blocks across adjacent segments
- **AND** all footer text SHALL remain readable on the light toolbar background
- **AND** the running compact footer row SHALL use the same toolbar background color as the completed prompt footer row
- **AND** the running compact footer row SHALL preserve segment emphasis such as bold model identity from the completed prompt footer row

#### Scenario: Footer segment casing is rendered

- **WHEN** Deepy builds footer segment labels other than case-sensitive file names
- **THEN** footer status keys SHALL use a consistent lowercase style
- **AND** case-sensitive file names such as `AGENTS.md` SHALL preserve their exact casing
- **AND** footer title keys `model`, `cwd`, `mcp`, `ctx`, and `newline` SHALL be bold while their values remain normal weight
- **AND** the loaded indicator `[AGENTS.md]` SHALL be bold

### Requirement: Todo Board Rendering

Deepy SHALL render the active todo plan as a compact terminal board instead of
raw tool JSON.

#### Scenario: Todo plan is created or updated

- **WHEN** a `todo_write` result updates the current todo plan
- **THEN** Deepy SHALL render a terminal todo board containing the current
  progress count and task list
- **AND** the board SHALL show pending, in-progress, and completed statuses with
  distinct visual markers
- **AND** the board SHALL use the active terminal theme palette for readable
  dark and light background output
- **AND** the board SHALL use the available terminal width instead of shrinking
  to content width

#### Scenario: Todo board summary is rendered

- **WHEN** the todo board is rendered for a non-empty todo plan
- **THEN** Deepy SHALL show the number of completed items and total items
- **AND** it SHALL show the current `in_progress` item when one exists
- **AND** it SHALL fall back to the first pending item when no item is marked
  `in_progress`
- **AND** it SHALL NOT duplicate runtime footer details such as model, context,
  elapsed time, or interrupt hints

#### Scenario: Todo board is rendered in a narrow terminal

- **WHEN** the terminal width or height cannot fit the complete todo board
- **THEN** Deepy SHALL truncate or compact the board without breaking table or
  block layout
- **AND** it SHALL preserve the progress count and current-task summary

#### Scenario: Todo tool output appears in history

- **WHEN** Deepy renders session history containing todo updates
- **THEN** it SHALL render the latest relevant todo state as a readable board or
  compact progress summary
- **AND** it SHALL NOT replay verbose raw todo JSON as ordinary transcript text
- **AND** todo detail output in history SHALL use the same compact block layout
  as live todo output

### Requirement: Todo Board Separation From Footer

Deepy SHALL keep todo board rendering separate from the interactive status
footer.

#### Scenario: Model turn is running

- **WHEN** a model turn is in progress and a todo plan exists
- **THEN** Deepy SHALL preserve the existing bottom footer layout and colors
- **AND** it SHALL NOT add the full todo list to the footer
- **AND** runtime status such as elapsed time, interrupt hint, thinking, and tool
  state SHALL remain in the dedicated runtime status line

#### Scenario: Model turn completes

- **WHEN** a model turn completes after todo updates
- **THEN** Deepy SHALL keep the latest todo board or compact todo summary
  visually consistent with the running-state board
- **AND** it SHALL NOT change the persistent footer style because todo state
  changed

### Requirement: Multiline Prompt Input Viewport

Deepy SHALL cap the visible height of multiline prompt input so composing long
prompts remains bounded inside the prompt editing area.

#### Scenario: Long multiline input exceeds visible prompt height

- **WHEN** a user enters multiline prompt text whose rendered height exceeds the
  prompt input viewport
- **THEN** Deepy SHALL keep the visible prompt input area within a configured
  maximum row count
- **AND** prompt-toolkit SHALL remain responsible for scrolling the editable
  prompt buffer
- **AND** Deepy SHALL leave room for the prompt footer when calculating the
  visible input cap

#### Scenario: Prompt cleanup is configured

- **WHEN** Deepy creates the interactive prompt session
- **THEN** Deepy SHALL configure prompt cleanup at session initialization
- **AND** Deepy SHALL NOT pass unsupported cleanup arguments to
  `PromptSession.prompt()`

### Requirement: Submitted Prompt Transcript

Deepy SHALL keep submitted user prompts visually consistent with transcript
output.

#### Scenario: User submits a prompt

- **WHEN** the user submits a non-empty prompt in the interactive terminal
- **THEN** Deepy SHALL clear the prompt_toolkit-rendered submitted prompt before
  printing the transcript copy
- **AND** Deepy SHALL print exactly one transcript copy using the existing green
  user-input style
- **AND** multiline submitted prompts SHALL preserve their prompt marker on the
  first line and continuation indentation on later lines
- **AND** submitted prompts that occupy multiple terminal rows SHALL remain
  visible above the runtime status row when active work begins immediately after
  submission

### Requirement: Experimental TUI Stable Command Alignment
The experimental Textual TUI SHALL align with stable terminal UI commands where
the behavior is meaningful in a full-screen Textual app.

#### Scenario: User opens help in TUI
- **WHEN** a user invokes `/help` or the equivalent command discovery action in
  the experimental TUI
- **THEN** the TUI SHALL show available commands, keybindings, model settings,
  session state, loaded skills, and config path in a readable Textual surface

#### Scenario: User opens status in TUI
- **WHEN** a user invokes `/status` in the experimental TUI
- **THEN** the TUI SHALL show project root, active model, reasoning mode, active
  session, context status, MCP status, loaded skills, and UI theme
- **AND** the status view SHALL be dismissible back to the active conversation

#### Scenario: User changes theme in TUI
- **WHEN** a user invokes `/theme` in the experimental TUI
- **THEN** the TUI SHALL allow selecting `dark` or `light`
- **AND** it SHALL persist the selected theme using Deepy's existing settings
  path
- **AND** it SHALL update or clearly report when restart is needed for full
  theme application

#### Scenario: User changes model in TUI
- **WHEN** a user invokes `/model` in the experimental TUI
- **THEN** the TUI SHALL allow selecting a supported model and reasoning mode
- **AND** it SHALL persist completed selections through Deepy's existing model
  settings flow
- **AND** cancelling before completion SHALL leave settings unchanged

### Requirement: Experimental TUI Init And Reset Parity
The experimental Textual TUI SHALL provide TUI-native behavior for `/init` and
`/reset` instead of leaving those stable commands unsupported.

#### Scenario: User runs init in TUI
- **WHEN** a user invokes `/init` in the experimental TUI
- **THEN** the TUI SHALL build the existing AGENTS.md initialization prompt for
  the active project root
- **AND** it SHALL submit that generated prompt through the normal TUI model
  turn path
- **AND** it SHALL preserve the active session continuation behavior used by
  normal prompts

#### Scenario: User runs init with extra instruction in TUI
- **WHEN** a user invokes `/init prefer concise guidance`
- **THEN** the TUI SHALL pass `prefer concise guidance` as the init prompt's
  extra instruction
- **AND** it SHALL NOT send the literal slash command as a normal model prompt

#### Scenario: User resets config in TUI
- **WHEN** a user invokes `/reset` in the experimental TUI
- **THEN** the TUI SHALL open a Textual-native configuration reset/setup surface
- **AND** submitting that surface SHALL delete or replace the configured TOML
  config using Deepy's existing config persistence helpers
- **AND** the TUI SHALL reload settings after the config is written
- **AND** subsequent TUI output SHALL use the newly saved UI theme when possible

#### Scenario: User cancels reset in TUI
- **WHEN** the user cancels the TUI reset/setup surface
- **THEN** the TUI SHALL leave the existing config and in-memory settings
  unchanged
- **AND** it SHALL return focus to the active conversation

#### Scenario: Reset cannot write config
- **WHEN** the TUI cannot determine a writable TOML config path
- **THEN** the TUI SHALL show a concise error
- **AND** it SHALL NOT delete existing settings or start a model turn

### Requirement: Experimental TUI Local Command Safety
The experimental Textual TUI SHALL avoid accidental model turns for commands
that are meant to be handled locally by the terminal UI.

#### Scenario: TUI receives a known local command
- **WHEN** the prompt text is a known Deepy slash command
- **THEN** the TUI SHALL route it through local TUI command handling
- **AND** it SHALL NOT send the command text to the model unless the command
  explicitly starts a model turn

#### Scenario: TUI receives an invalid command form
- **WHEN** the prompt text starts with `/` but does not match a supported command
  or skill invocation
- **THEN** the TUI SHALL show a concise command error
- **AND** it SHALL keep the user's prompt context recoverable

#### Scenario: TUI receives a local command
- **WHEN** the prompt text starts with `!` after trimming
- **THEN** the TUI SHALL route the prompt through Deepy's local command mode
- **AND** it SHALL NOT send the prompt text to the model

#### Scenario: TUI receives an empty local command
- **WHEN** the user submits `!` with no command text after it
- **THEN** the TUI SHALL show a concise usage message
- **AND** it SHALL NOT start a model turn
- **AND** it SHALL NOT append a local command transcript to the session

### Requirement: Experimental TUI Local Command Execution
The experimental Textual TUI SHALL execute user-entered `!command` prompts by
reusing Deepy's existing local command execution helpers and rendering the
result through TUI shell output blocks.

#### Scenario: POSIX local command runs in TUI
- **WHEN** the TUI handles a non-empty local command on macOS or Linux
- **THEN** it SHALL use Deepy's existing POSIX PTY-backed local command runner
- **AND** it SHALL render command output, exit status, truncation, timeout, and
  interruption metadata in the transcript

#### Scenario: Windows PowerShell local command runs in TUI
- **WHEN** the TUI handles a non-empty local command on Windows with PowerShell
  or PowerShell Core detected
- **THEN** it SHALL use Deepy's existing non-interactive pipe-based Windows
  local command runner
- **AND** it SHALL NOT allocate a Windows pseudo-terminal or depend on
  `pywinpty`
- **AND** it SHALL invoke the shell with the detected PowerShell command
  dialect
- **AND** it SHALL decode Windows-compatible output, normalize line endings,
  and remove terminal control sequences before rendering
- **AND** it SHALL report shell kind, command dialect, TTY mode, cwd, exit code,
  duration, timeout, and interruption metadata when available

#### Scenario: Windows cmd local command boundary in TUI
- **WHEN** the TUI handles a non-empty local command on Windows with `cmd.exe`
  detected
- **THEN** the TUI MAY reuse Deepy's existing non-interactive `cmd` dialect path
- **AND** if the TUI implementation does not support that shell path, it SHALL
  show a clear unsupported message
- **AND** it SHALL NOT allocate a pseudo-terminal, call the model, or treat the
  command as normal prompt text

#### Scenario: TUI local command tries interactive terminal behavior
- **WHEN** a Windows local command requires interactive stdin, an editor, a
  pager, or full-screen terminal UI
- **THEN** the TUI SHALL preserve Deepy's non-interactive Windows boundary
- **AND** it SHALL render captured output or failure state without corrupting
  subsequent prompt input

### Requirement: Experimental TUI Skill Market Management
The experimental Textual TUI SHALL connect Deepy's skill market and full skill
management flows instead of limiting `/skills` to local list/use/show output.

#### Scenario: User opens skill management in TUI
- **WHEN** a user invokes `/skills` without arguments in the experimental TUI
- **THEN** the TUI SHALL open a Textual skill management surface
- **AND** the surface SHALL distinguish installed/local skills from market
  skills
- **AND** it SHALL provide keyboard navigation and a clear return path to the
  conversation

#### Scenario: User searches market skills in TUI
- **WHEN** a user invokes `/skills search pdf`
- **THEN** the TUI SHALL show matching market skills or a concise market access
  error
- **AND** it SHALL NOT start a model turn

#### Scenario: User installs a market skill in TUI
- **WHEN** a user invokes `/skills install NAME` or selects install from the TUI
  skill management surface
- **THEN** the TUI SHALL use Deepy's existing skill market install helper
- **AND** it SHALL collect user/project install scope when required
- **AND** it SHALL show success or failure without dumping package contents into
  the main transcript

#### Scenario: User updates or removes market skills in TUI
- **WHEN** a user invokes `/skills uninstall NAME`, `/skills installed`,
  `/skills update NAME`, or `/skills update --all`
- **THEN** the TUI SHALL use Deepy's existing skill market helpers
- **AND** it SHALL keep loaded skill state consistent with installed and removed
  skills

#### Scenario: User views a skill in TUI
- **WHEN** a user views a local, installed, or market skill from the TUI
- **THEN** the TUI SHALL show details in a dedicated Textual surface
- **AND** it SHALL avoid dumping full `SKILL.md` bodies into the main transcript

### Requirement: Experimental TUI Exit Summary
The experimental Textual TUI SHALL provide a clean exit path consistent with
Deepy's stable terminal experience.

#### Scenario: User exits active TUI session
- **WHEN** the user exits the experimental TUI through `/exit`, `/quit`, or confirmed Ctrl+D
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL return terminal control without leaving a stale full-screen
  status area
- **AND** it SHALL show the redesigned concise exit summary panel after leaving the full-screen app
- **AND** the panel SHALL use the same compact local-only exit summary content as the stable terminal UI
- **AND** it SHALL NOT call the DeepSeek balance endpoint
- **AND** it SHALL NOT display DeepSeek balance information

### Requirement: Stable Input Suggestion Ghost Text
Deepy's stable prompt-toolkit terminal UI SHALL render input suggestions as
prompt-area ghost text without changing existing prompt submission semantics.

#### Scenario: Suggestion becomes visible
- **WHEN** an eligible input suggestion is available
- **AND** the stable terminal prompt input buffer is empty
- **THEN** Deepy SHALL show the suggestion in the input area using muted or
  placeholder-style ghost text
- **AND** it SHALL keep the normal prompt footer and transcript readable

#### Scenario: User accepts with Tab
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the user presses Tab
- **THEN** Deepy SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: User accepts with Right Arrow
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the user presses Right Arrow
- **THEN** Deepy SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: User presses Enter with visible suggestion
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the input buffer is empty
- **AND** the user presses Enter
- **THEN** Deepy SHALL NOT insert or submit the suggestion
- **AND** Enter SHALL retain the stable prompt's existing submit behavior

#### Scenario: User starts editing
- **WHEN** ghost-text input suggestion is visible in the stable terminal UI
- **AND** the user types, pastes, opens another completion surface, submits a
  prompt, starts a local command, or starts a model turn
- **THEN** Deepy SHALL clear the visible suggestion

### Requirement: Input Suggestion Slash Command
Deepy's interactive terminal UIs SHALL expose `/input-suggestion` as the user
control for input suggestion enablement.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/input-suggestion` SHALL be included as a built-in command
- **AND** its description SHALL indicate that it toggles input suggestions

#### Scenario: User toggles input suggestions
- **WHEN** a user runs `/input-suggestion` with no arguments
- **THEN** Deepy SHALL toggle the persisted input suggestion enabled state
- **AND** it SHALL update the current interactive process to use the new state
- **AND** it SHALL print a concise confirmation of whether input suggestions
  are enabled or disabled

#### Scenario: User provides unsupported arguments
- **WHEN** a user runs `/input-suggestion` with any argument
- **THEN** Deepy SHALL reject the command with a concise usage message
- **AND** it SHALL leave the saved input suggestion setting unchanged

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/input-suggestion` in the command list

### Requirement: Interactive Status Command
Deepy SHALL provide a discoverable `/status` command in the stable interactive terminal UI that renders a compact status panel with local usage, context, runtime, and DeepSeek balance information.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds stable interactive slash command completions
- **THEN** `/status` SHALL be included as a built-in command
- **AND** its description SHALL explain that it shows status, usage, and DeepSeek balance

#### Scenario: Help lists status command
- **WHEN** the user runs `/help` in the stable interactive terminal UI
- **THEN** Deepy SHALL list `/status`
- **AND** the help text SHALL describe the command as a status, usage, and balance view

#### Scenario: User runs status command
- **WHEN** the user runs `/status` in the stable interactive terminal UI
- **THEN** Deepy SHALL render a compact status panel
- **AND** the panel SHALL include the active model and reasoning mode
- **AND** the panel SHALL include whether an API key is configured without printing the key
- **AND** the panel SHALL include active-session Token Usage when an active session exists and usage is known
- **AND** the panel SHALL include project-level Token Usage when persisted session usage is known
- **AND** the panel SHALL include Context Window occupancy when known
- **AND** the panel SHALL include project root, session count, skill count, and MCP status
- **AND** the panel SHALL include DeepSeek balance status returned for that `/status` invocation

#### Scenario: Balance lookup fails
- **WHEN** the user runs `/status`
- **AND** Deepy cannot retrieve DeepSeek balance because of missing configuration, unsupported API host, timeout, network failure, authentication failure, or malformed response
- **THEN** Deepy SHALL still render the rest of the status panel
- **AND** it SHALL show concise balance unavailable text
- **AND** it SHALL NOT print a traceback

#### Scenario: Other terminal surfaces render status
- **WHEN** Deepy renders welcome content, prompt footer content, working status content, local command status content, usage footers, or normal model-turn output
- **THEN** Deepy SHALL NOT call the DeepSeek balance endpoint
- **AND** it SHALL NOT add balance information to those frequently rendered surfaces

### Requirement: Redesigned Exit Summary Panel
Deepy SHALL render a compact exit summary panel in the stable interactive
terminal UI with local usage and DeepSeek session-cost information when
available.

#### Scenario: User exits stable interactive session
- **WHEN** the user exits the stable interactive terminal UI through `/exit`,
  `/quit`, or confirmed Ctrl+D
- **THEN** Deepy SHALL render an exit summary panel
- **AND** the panel SHALL use the same compact visual language and label
  hierarchy as the `/status` panel
- **AND** the panel SHALL include local cumulative model usage when known
- **AND** the panel SHALL include input-suggestion usage when known
- **AND** the panel SHALL include the active model and session identity when
  known
- **AND** the panel SHALL include DeepSeek session cost when a reliable
  start/end account balance delta is available
- **AND** the panel SHALL label the cost as based on the DeepSeek account
  balance delta during the session
- **AND** the panel SHALL remain readable when usage or cost is unknown

#### Scenario: Exit summary has no usage
- **WHEN** the user exits a stable interactive session with no known usage
- **THEN** Deepy SHALL still render a concise exit summary panel
- **AND** it SHALL omit empty usage tables instead of showing zero-filled noise

#### Scenario: Session cost cannot be computed
- **WHEN** Deepy cannot retrieve starting or ending balance, cannot parse a
  balance response, or cannot compute a reliable positive balance delta
- **THEN** the stable exit summary SHALL still render
- **AND** it SHALL keep local usage information visible
- **AND** it SHALL show concise cost unavailable text when cost tracking was
  attempted
- **AND** it SHALL NOT print a traceback

### Requirement: Stable Windows Prompt Bottom Anchor

Deepy's stable prompt-toolkit terminal UI SHALL preserve submitted prompt
transcript visibility on Windows when active work starts immediately after a
prompt submitted from the terminal bottom.

#### Scenario: Windows submitted prompt reaches terminal bottom

- **WHEN** the user runs the stable terminal UI in Windows Terminal or another
  Windows console-backed TTY
- **AND** the user submits a non-empty prompt whose transcript copy would start
  active work while the cursor is on the final visible terminal row
- **THEN** Deepy SHALL detect that bottom-row cursor position on Windows
- **AND** it SHALL create scrollable transcript space before drawing the runtime
  status row
- **AND** the submitted prompt transcript copy SHALL remain visible above the
  runtime status row

#### Scenario: Windows submitted prompt is not at terminal bottom

- **WHEN** the user runs the stable terminal UI in a Windows console-backed TTY
- **AND** the user submits a non-empty prompt while the cursor is not on the
  final visible terminal row
- **THEN** Deepy SHALL NOT add bottom-anchor scroll space solely because the
  platform is Windows
- **AND** normal transcript output SHALL continue from the current cursor
  position

#### Scenario: Windows cursor position cannot be read

- **WHEN** Deepy cannot read the Windows console cursor position for a stable UI
  prompt submission
- **THEN** Deepy SHALL continue the turn without crashing
- **AND** it SHALL keep the runtime status row clearable at turn completion
- **AND** any fallback bottom-anchor behavior SHALL be limited to Windows TTY
  submissions where preserving transcript visibility is more important than
  avoiding one extra blank line

#### Scenario: POSIX terminal behavior is preserved

- **WHEN** the user runs the stable terminal UI in a POSIX terminal
- **AND** the terminal supports the existing ANSI cursor report path
- **THEN** Deepy SHALL continue using that path for bottom-anchor detection
- **AND** the Windows cursor detection path SHALL NOT run

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

### Requirement: Interactive Configuration Reset
Deepy SHALL reset terminal configuration without leaving partial files.

#### Scenario: Reset setup is interrupted
- **WHEN** a user exits or the prompt stream ends during `/reset` setup
- **THEN** Deepy SHALL report the cancellation without printing a traceback
- **AND** if a config file existed before `/reset`, Deepy SHALL restore that
  file unchanged
- **AND** if no config file existed before `/reset`, Deepy SHALL leave no
  partial config file behind

#### Scenario: Reset changes running UI or theme selection
- **WHEN** a user completes `/reset` setup in the stable terminal UI
- **AND** the selected UI or theme differs from the currently running stable UI
  or theme selection
- **THEN** Deepy SHALL tell the user that restarting Deepy is required for the
  UI and theme selection to take effect

### Requirement: Safe Malformed Tool Argument Display
Deepy's stable terminal UI SHALL summarize malformed v3 file-tool arguments
without dumping large raw mutation payloads into the transcript.

#### Scenario: Malformed write arguments are rendered
- **WHEN** Deepy renders a `Write` tool call or output whose arguments are not
  valid JSON
- **THEN** the stable terminal UI SHALL show the normalized `[Write]` label
- **AND** it SHALL show a bounded malformed-arguments summary with the target
  path when it can be extracted safely
- **AND** it SHALL NOT render raw `content` body text solely because argument
  parsing failed

#### Scenario: Malformed update arguments are rendered
- **WHEN** Deepy renders an `Update` tool call or output whose arguments are not
  valid JSON
- **THEN** the stable terminal UI SHALL show the normalized `[Update]` label
- **AND** it SHALL show a bounded malformed-arguments summary with target path
  or edit-count hints when they can be extracted safely
- **AND** it SHALL NOT render raw `old`, `new`, or edit body text solely because
  argument parsing failed

#### Scenario: Malformed read arguments are rendered
- **WHEN** Deepy renders a `Read` tool call or output whose arguments are not
  valid JSON
- **THEN** the stable terminal UI SHALL show the normalized `[Read]` label
- **AND** it SHALL show a bounded malformed-arguments summary with target path
  hints when they can be extracted safely

### Requirement: Retryable Tool Failure Presentation
Deepy's stable terminal UI SHALL present retryable argument failures differently
from blocking tool execution failures.

#### Scenario: Retryable invalid arguments are shown
- **WHEN** a tool result has `error_code="invalid_arguments"` and
  `retryable=true`
- **THEN** the stable terminal UI SHALL render the tool status as retryable or
  recoverable rather than as an ordinary blocking failure
- **AND** it SHALL include a concise recovery detail when available
- **AND** it SHALL keep the existing normalized tool label style for `Read`,
  `Write`, and `Update`

#### Scenario: Blocking mutation failure is shown
- **WHEN** a `Write` or `Update` result fails because of a blocking safety or
  mutation error
- **THEN** the stable terminal UI SHALL continue to render it as a failed tool
  result
- **AND** it SHALL NOT imply that the mutation was recovered unless a later
  successful tool result explicitly reports success

### Requirement: Background Task Slash Commands
Deepy's stable terminal UI SHALL provide `/ps` and `/stop` commands for managing Deepy-owned background tasks.

#### Scenario: User lists background tasks
- **WHEN** a user runs `/ps`
- **THEN** Deepy SHALL print running and recent terminal background tasks
- **AND** each task row SHALL include task id, status, elapsed or finished time, and concise command or description
- **AND** the output SHALL include enough information for the user to request task output or identify work to stop

#### Scenario: User lists tasks when none exist
- **WHEN** a user runs `/ps` and Deepy has no managed background tasks
- **THEN** Deepy SHALL print a concise no-background-tasks message
- **AND** it SHALL keep the active session unchanged

#### Scenario: User stops background tasks
- **WHEN** a user runs `/stop`
- **THEN** Deepy SHALL request termination for all running background tasks owned by the current Deepy process/session
- **AND** it SHALL print a concise summary of tasks that were requested to stop
- **AND** it SHALL keep terminal tasks visible in `/ps` after they settle

#### Scenario: User stops when no tasks are running
- **WHEN** a user runs `/stop` and no managed background tasks are running
- **THEN** Deepy SHALL print a concise no-running-background-tasks message
- **AND** it SHALL keep the active session unchanged

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL list `/ps` and `/stop` with concise descriptions

### Requirement: Background Task Status Non-Interference
Deepy's stable terminal UI SHALL keep background task status separate from active model thinking and response rendering.

#### Scenario: Background task runs while prompt is idle
- **WHEN** one or more background tasks are running while Deepy is waiting for input
- **THEN** Deepy MAY show a concise background task count in prompt/status context
- **AND** it SHALL NOT print unsolicited task output into the transcript

#### Scenario: Background task runs during model turn
- **WHEN** one or more background tasks are running during a foreground model turn
- **THEN** Deepy SHALL preserve the foreground working status, thinking stream, tool display, and assistant response rendering
- **AND** background task output SHALL remain hidden unless explicitly inspected

### Requirement: Background Task Exit Cleanup
Deepy's stable terminal UI SHALL clean up background tasks during interactive exit.

#### Scenario: User exits with slash command
- **WHEN** the user runs `/exit` or `/quit`
- **THEN** Deepy SHALL stop all running managed background tasks before closing the interactive runtime
- **AND** it SHALL still print the normal exit summary

#### Scenario: User exits with Ctrl+D confirmation
- **WHEN** the user confirms exit with Ctrl+D while background tasks are running
- **THEN** Deepy SHALL stop all running managed background tasks before closing the interactive runtime
- **AND** it SHALL still print the normal exit summary

#### Scenario: User interrupts the terminal UI
- **WHEN** the user exits the stable terminal UI with KeyboardInterrupt
- **THEN** Deepy SHALL attempt bounded cleanup of all running managed background tasks before returning control to the terminal

### Requirement: Subagent Lifecycle Rendering

Deepy's stable terminal UI SHALL render subagent lifecycle events clearly and
compactly.

#### Scenario: Subagent starts

- **WHEN** a subagent starts during a model turn
- **THEN** the terminal UI SHALL render a concise subagent start line
- **AND** the line SHALL include the subagent name and assigned task summary

#### Scenario: Subagent completes

- **WHEN** a subagent completes during a model turn
- **THEN** the terminal UI SHALL render a concise completion line
- **AND** the line SHALL include a readable result summary

#### Scenario: Subagent completes with report about rejected approval

- **WHEN** a subagent completes successfully
- **AND** its structured report text mentions an audit approval rejection
- **THEN** the terminal UI SHALL render the subagent as successful
- **AND** it SHALL NOT render the subagent lifecycle line as rejected solely because of report text

#### Scenario: Subagent needs approval

- **WHEN** a subagent reaches a command approval-required state
- **THEN** the terminal UI SHALL preserve the approval question flow
- **AND** it SHALL show the command and policy reason clearly enough for the user
  to decide

#### Scenario: Subagent fails

- **WHEN** a subagent fails, times out, or is blocked
- **THEN** the terminal UI SHALL render a concise failure or blocked line
- **AND** the active Deepy session SHALL remain usable

### Requirement: Subagent Output Non-Interference

Deepy's stable terminal UI SHALL keep subagent output from corrupting main-agent
thinking and response rendering.

#### Scenario: Subagent emits nested output

- **WHEN** a subagent emits nested thinking, tool calls, or raw output
- **THEN** the terminal UI SHALL keep the main transcript readable
- **AND** it SHALL avoid interleaving raw nested output into the main assistant
  response

#### Scenario: User requests details

- **WHEN** the user asks for subagent details or the main agent needs to cite a
  subagent result
- **THEN** Deepy MAY show or summarize the relevant subagent details
- **AND** it SHALL preserve the concise lifecycle summary in the normal
  transcript

### Requirement: Stable Slash Command Discovery Ranking
Deepy's stable prompt-toolkit UI SHALL rank slash command completions by user
intent and command relevance rather than by implementation category alone.

#### Scenario: Bare slash discovery includes task entry points
- **WHEN** the stable interactive prompt builds completions for a bare `/`
- **THEN** Deepy SHALL include built-in commands, subagent commands, and skill
  invocation commands in the completion candidate set
- **AND** common workflow commands SHALL appear before lower-frequency
  management or exit commands
- **AND** subagent commands SHALL be discoverable without requiring the user to
  type a subagent-specific prefix

#### Scenario: Typed slash search ranks useful matches
- **WHEN** the user types a partial slash command token
- **THEN** exact command-name matches SHALL rank before prefix matches
- **AND** prefix matches SHALL rank before weaker description or substring
  matches
- **AND** ties SHALL use the shared slash command priority and then stable
  alphabetical ordering

#### Scenario: Skill completions show metadata
- **WHEN** the stable UI renders skill slash completions
- **THEN** each skill completion SHALL expose the skill label and description
  when available
- **AND** loaded skills SHALL be distinguishable from unloaded skills
- **AND** loaded skills SHALL rank ahead of otherwise equivalent unloaded skill
  completions

#### Scenario: File mention completion is unaffected
- **WHEN** slash command completions and file mention completions are both
  available through the stable prompt input
- **THEN** slash command ranking SHALL NOT prevent file mention completions from
  appearing for `@` file tokens
- **AND** file mention completions SHALL NOT reorder slash command candidates
  for `/` command tokens

### Requirement: Runtime Bottom Status Stability

Deepy SHALL render active-work runtime status as a terminal-safe single line that preserves critical progress information and bounded command detail.

#### Scenario: Long tool payload is displayed during active work

- **WHEN** a model turn is active and the current tool status includes a long parameter payload
- **THEN** Deepy SHALL keep the runtime status within the terminal-bottom row without uncontrolled wrapping or scrolling
- **AND** it SHALL keep the spinner, elapsed time, and interrupt affordance visible when the terminal width can fit them
- **AND** it SHALL prefer truncating payload detail before truncating the runtime prefix

#### Scenario: Long local command is displayed during execution

- **WHEN** a local `!cmd` command is running and the command text is longer than the available status payload width
- **THEN** Deepy SHALL continue to show command text in the runtime status when the terminal width can fit payload detail
- **AND** it SHALL tail-truncate the command payload so the beginning of the command remains visible
- **AND** it SHALL keep the spinner, elapsed time, and interrupt affordance visible when the terminal width can fit them

#### Scenario: Long shell tool command is displayed during execution

- **WHEN** a shell tool call is active and the shell command text is longer than the available status payload width
- **THEN** Deepy SHALL continue to show the shell tool label and command text in the runtime status when the terminal width can fit payload detail
- **AND** it SHALL tail-truncate the command payload so the beginning of the command remains visible
- **AND** it SHALL keep the spinner, elapsed time, and interrupt affordance visible when the terminal width can fit them

#### Scenario: Runtime payload contains control characters

- **WHEN** runtime status detail contains newlines, carriage returns, tabs, ANSI escape sequences, or non-printing control characters
- **THEN** Deepy SHALL normalize the detail to printable single-line status text before writing it to the terminal-bottom row
- **AND** the normalized status SHALL NOT move the cursor, clear terminal content, create extra terminal rows, or displace the protected runtime prefix

#### Scenario: Runtime status is rendered in a narrow terminal

- **WHEN** the terminal width is too narrow to fit the full runtime status
- **THEN** Deepy SHALL reduce payload detail before reducing the activity label
- **AND** it SHALL reduce the activity label before reducing the spinner, elapsed time, and interrupt affordance
- **AND** it SHALL still write no more than one terminal-bottom row

### Requirement: Stable Terminal Sessions Survive Storage Replacement
Deepy's stable terminal UI SHALL preserve user-facing session behavior while the
underlying active session store changes.

#### Scenario: User resumes a stored session
- **WHEN** a user opens `/resume` in the stable terminal UI
- **THEN** Deepy SHALL show sessions from the active transactional session store
  with first prompt, status, time, and history estimate when known
- **AND** selected history SHALL be rendered using the same transcript display
  conventions as live output

#### Scenario: User runs session list command
- **WHEN** a user runs the stable terminal session listing command
- **THEN** Deepy SHALL list sessions from the active transactional session store
- **AND** it SHALL NOT list sessions that exist only as historical JSONL files
  or `sessions-index.json` entries

#### Scenario: User compacts active session
- **WHEN** a user runs `/compact` while an active stable terminal session has
  compactable history
- **THEN** Deepy SHALL run durable session compaction against the active
  transactional session store
- **AND** the active session SHALL remain resumable after compaction succeeds

#### Scenario: Stable terminal command records local transcript
- **WHEN** a stable terminal local command-mode command completes
- **THEN** Deepy SHALL persist the synthetic shell transcript records in the
  active transactional session store
- **AND** later resume and model replay SHALL see the stored local command
  transcript

### Requirement: Cache Health Status Display
The default terminal UI SHALL expose DeepSeek cache health when cache usage data
is available.

#### Scenario: Usage includes cache tokens
- **WHEN** a model turn completes with cache hit and miss token data
- **THEN** the terminal UI SHALL be able to show fresh input tokens, cached
  input tokens, and cache hit ratio
- **AND** it SHALL use the normalized usage values persisted for the session

#### Scenario: Cache usage is unknown
- **WHEN** the active provider or model turn does not report cache hit and miss
  token data
- **THEN** the terminal UI SHALL show cache health as unknown or omit the cache
  metric
- **AND** it SHALL NOT imply a zero percent cache hit ratio

#### Scenario: Status command is rendered
- **WHEN** the user opens `/status`
- **THEN** Deepy SHALL include the active prefix generation, session cache hit
  ratio when known, and latest cache-break reason when present

### Requirement: Cache Break Visibility
The default terminal UI SHALL surface cache-breaking context changes without
interrupting the user's workflow.

#### Scenario: Cache break occurs during a turn
- **WHEN** Deepy records a cache break from compaction, retry recovery, interrupt
  cleanup, prefix change, or tool-set change
- **THEN** the terminal UI SHALL make the reason available in status or usage
  surfaces
- **AND** it SHALL keep the reason concise enough for terminal display

#### Scenario: Cache metadata contains secrets
- **WHEN** cache health or cache break information is rendered
- **THEN** the terminal UI SHALL NOT print API keys, authorization headers, or
  full provider payloads

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

### Requirement: Audit Mode Status Display

Deepy's stable terminal UI SHALL make the active system audit mode visible
during interactive use.

#### Scenario: Prompt footer shows audit mode

- **WHEN** the stable interactive prompt is waiting for user input
- **THEN** the prompt footer SHALL include the active audit mode
- **AND** the footer SHALL keep existing model, working-directory, MCP, and
  context status segments readable

#### Scenario: Status panel shows audit mode

- **WHEN** the user opens a status surface such as `/status`
- **THEN** Deepy SHALL include the active audit mode
- **AND** it SHALL include whether the mode came from runtime state or persisted
  configuration when that distinction is available

### Requirement: Audit Mode Keyboard Cycling

Deepy's stable prompt-toolkit UI SHALL support cycling audit modes with
`Shift+Tab`.

#### Scenario: User cycles audit mode

- **WHEN** the user presses `Shift+Tab` while the stable prompt is active
- **THEN** Deepy SHALL switch to the next audit mode in the order `normal`,
  `auto`, `yolo`, `normal`
- **AND** Deepy SHALL update the visible prompt footer without submitting the
  current prompt text

#### Scenario: Tab completion remains available

- **WHEN** the user presses `Tab` without `Shift`
- **THEN** Deepy SHALL preserve the existing completion and input-suggestion
  behavior
- **AND** it SHALL NOT cycle the audit mode

### Requirement: Approval Prompt Display

Deepy's terminal UI SHALL present SDK approval interruptions as explicit approval
prompts rather than normal assistant questions.

#### Scenario: Built-in tool approval prompt is displayed

- **WHEN** an SDK run pauses for approval of a built-in side-effect tool
- **THEN** Deepy SHALL render an approval prompt that identifies the action kind,
  tool name, arguments summary, and relevant target command, path, or task id
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: MCP approval prompt is displayed

- **WHEN** an SDK run pauses for approval of an MCP tool call
- **THEN** Deepy SHALL render an approval prompt that identifies the MCP server,
  MCP tool, and arguments summary
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: Approval prompt is not transcript noise

- **WHEN** Deepy renders an approval prompt
- **THEN** it SHALL distinguish the prompt from model-authored
  `AskUserQuestion` content
- **AND** it SHALL NOT submit the approval prompt text as a normal user message

#### Scenario: Rejected approval resumes the turn

- **WHEN** the user rejects an approval prompt
- **THEN** Deepy SHALL resume the paused SDK run with a rejection result
- **AND** the terminal UI SHALL continue rendering subsequent assistant output
  from the resumed run

### Requirement: Task-Focused Audit Approval Panels

Deepy's stable terminal UI SHALL render audit approval prompts as concise
task-focused decision panels rather than raw SDK argument dumps.

#### Scenario: Shell command approval uses task summary

- **WHEN** an SDK approval interruption requests a shell command execution
- **THEN** Deepy SHALL show a title that identifies the request as a shell
  command approval
- **AND** it SHALL show the command as the primary target
- **AND** it SHALL show meaningful secondary context such as description or
  working directory when available
- **AND** it SHALL NOT show raw internal field labels such as `action`, `agent`,
  or `arguments.*` unless no typed summary can be derived

#### Scenario: MCP approval uses server and tool summary

- **WHEN** an SDK approval interruption requests an MCP tool call
- **THEN** Deepy SHALL show a title that identifies the request as an MCP tool
  approval
- **AND** it SHALL show the MCP server and tool as the primary target
- **AND** it SHALL show only the most relevant bounded argument fields, such as
  `url`, `urls`, `query`, or `format`, when available
- **AND** it SHALL NOT render the full raw argument JSON by default

#### Scenario: Unknown approval falls back to bounded summary

- **WHEN** an SDK approval interruption cannot be classified as shell, file
  mutation, or MCP
- **THEN** Deepy SHALL show the tool name and a bounded structured argument
  summary
- **AND** the fallback summary SHALL remain visually distinct from normal
  assistant messages

### Requirement: File Mutation Approval Diff Review

Deepy's stable terminal UI SHALL render `Write` and `Update` audit approvals
with highlighted diff previews and relative target paths when possible.

#### Scenario: Missing update diff context uses safe fallback

- **WHEN** an `Update` approval does not contain enough before-and-after
  information to derive a reliable diff
- **THEN** Deepy SHALL show a compact typed summary instead of fabricating a diff
- **AND** it SHALL still display the target path using the relative-path rules
- **AND** the typed summary SHALL show the number of edits when available
- **AND** it SHALL NOT show a structured `summary` argument block or raw old/new
  argument content

### Requirement: Approval Prompt Keyboard Interaction

Deepy's stable terminal approval picker SHALL resolve approvals only through
navigation selection, `Enter`, and `Esc`.

#### Scenario: Arrow keys move selection

- **WHEN** an approval prompt is active
- **AND** the user presses `Up` or `Down`
- **THEN** Deepy SHALL move the selection among visible approval controls,
  including auxiliary inspect controls and final decisions
- **AND** it SHALL NOT approve or reject the tool call only because selection
  moved

#### Scenario: Enter activates selected control

- **WHEN** an approval prompt is active
- **AND** the user presses `Enter`
- **AND** the selected control is `Approve` or `Reject`
- **THEN** Deepy SHALL resolve the SDK approval with the selected decision

#### Scenario: Enter on inspect control does not resolve approval

- **WHEN** an approval prompt is active
- **AND** the selected control is an auxiliary expand or collapse control
- **AND** the user presses `Enter`
- **THEN** Deepy SHALL toggle the displayed preview state
- **AND** it SHALL keep the approval prompt active

#### Scenario: Escape rejects approval

- **WHEN** an approval prompt is active
- **AND** the user presses `Esc`
- **THEN** Deepy SHALL resolve the SDK approval as rejected

#### Scenario: Letter shortcuts do not resolve approval

- **WHEN** an approval prompt is active
- **AND** the user presses `Y`, `A`, `N`, `R`, or their lowercase equivalents
- **THEN** Deepy SHALL NOT resolve the SDK approval because of that keypress
- **AND** visible approval hints SHALL NOT advertise those letter shortcuts

### Requirement: Stable UI Image Paste Attachments
Deepy SHALL support non-blocking clipboard image paste handling in the stable prompt-toolkit terminal UI.

#### Scenario: User pastes image into supported model prompt
- **WHEN** the stable terminal UI is focused on the prompt
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model supports image input
- **THEN** Deepy SHALL attach the image to the current prompt draft
- **AND** it SHALL insert the attachment label into the prompt input text as `[图片1]`, `[图片2]`, or the next available image label
- **AND** it SHALL preserve existing prompt text and cursor-editing behavior

#### Scenario: User deletes image label from prompt input
- **WHEN** a stable terminal UI prompt draft contains an inserted image label
- **AND** the user deletes that label from the prompt text before submission
- **THEN** Deepy SHALL remove the corresponding image attachment from the draft
- **AND** it SHALL NOT send that image with the next prompt submission

#### Scenario: User deletes within image label from prompt input
- **WHEN** a stable terminal UI prompt draft contains an inserted image label
- **AND** the cursor is inside the label or immediately after the label
- **AND** the user presses Backspace
- **THEN** Deepy SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft
- **WHEN** the cursor is inside the label or immediately before the label
- **AND** the user presses Delete
- **THEN** Deepy SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft

#### Scenario: User pastes image into unsupported model prompt
- **WHEN** the stable terminal UI is focused on the prompt
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model does not support image input
- **THEN** Deepy SHALL append a concise assistant-visible message to the transcript
- **AND** it SHALL NOT show the rejection only in the status/footer bar
- **AND** it SHALL discard the pasted image
- **AND** it SHALL preserve the current prompt text
- **AND** it SHALL keep accepting text input

#### Scenario: User submits prompt with images
- **WHEN** a stable terminal UI prompt draft contains text and image attachments
- **AND** the user presses Enter
- **THEN** Deepy SHALL submit the text and image attachments as one user turn
- **AND** the displayed user transcript block SHALL include the prompt text and compact image labels
- **AND** it SHALL NOT display raw base64 data

#### Scenario: User inserts newline with image attachments
- **WHEN** a stable terminal UI prompt draft contains image attachments
- **AND** the user presses Ctrl+J
- **THEN** Deepy SHALL insert a newline into the prompt text
- **AND** it SHALL NOT submit the prompt
- **AND** it SHALL NOT remove the image attachments

#### Scenario: User pastes text
- **WHEN** the stable terminal UI receives pasted text without clipboard image data
- **THEN** Deepy SHALL preserve the existing text paste behavior
- **AND** it SHALL NOT create image attachments

### Requirement: Syntax Highlighting Consistency
Deepy SHALL render syntax-highlighted terminal code and diff content with
surface-consistent backgrounds and XML-family language recognition.

#### Scenario: XML code block uses a coherent background
- **WHEN** the stable terminal UI renders an assistant Markdown fenced code block
  tagged as XML or a recognized XML-family language
- **THEN** syntax-highlighted token foreground colors SHALL remain visible
- **AND** token backgrounds SHALL match the code block background instead of
  creating patchy theme-background blocks

#### Scenario: XML diff preserves multiline syntax
- **WHEN** the stable terminal UI renders a `Write` or `Update` diff preview for
  XML content with multiline tags, attributes, comments, or CDATA
- **THEN** Deepy SHALL preserve XML syntax highlighting across the related diff
  lines
- **AND** added and removed line backgrounds, gutters, markers, and truncation
  behavior SHALL remain unchanged

#### Scenario: XML-like files use XML highlighting
- **WHEN** the stable terminal UI renders code or diff content for a recognized
  XML-family file type such as SVG, XAML, C# project files, MSBuild props or
  targets files, or well-known XML-based config files
- **THEN** Deepy SHALL use XML syntax highlighting instead of falling back to
  unhighlighted plain text

#### Scenario: Non-XML syntax highlighting is preserved
- **WHEN** the stable terminal UI renders code or diff content for already
  supported mainstream languages such as Python, JavaScript, TypeScript, TSX,
  JSON, YAML, TOML, Rust, CSS, shell, or SQL
- **THEN** Deepy SHALL preserve existing syntax highlighting behavior
- **AND** unsupported or unknown languages SHALL continue to fall back to
  readable plain text rather than failing rendering

### Requirement: Shared Theme Contract With Textual Theme Mapping
Deepy SHALL preserve the shared `dark` and `light` UI theme contract while
allowing the Textual TUI to map those values to richer Textual-native themes.

#### Scenario: Stable UI reads theme settings
- **WHEN** the default stable terminal UI reads `ui.theme`
- **THEN** it SHALL continue to accept `dark` and `light`
- **AND** it SHALL NOT be required to understand Textual-only theme names

#### Scenario: Textual TUI reads theme settings
- **WHEN** the Textual TUI reads `ui.theme`
- **THEN** it MAY map `dark` and `light` to curated Textual built-in themes
- **AND** the mapping SHALL remain internal to the Textual TUI unless a separate
  TUI-specific config field is introduced
- **AND** the default `dark` mapping SHALL use `tokyo-night`

#### Scenario: Textual TUI reads a TUI-specific theme override
- **WHEN** `ui.textual_theme` contains a supported Textual theme name
- **THEN** the Textual TUI MAY apply that theme instead of the shared
  `ui.theme` mapping
- **AND** the stable UI SHALL ignore the TUI-specific theme override

#### Scenario: User selects shared theme
- **WHEN** the user selects `/theme dark` or `/theme light`
- **THEN** Deepy SHALL persist the selected shared theme value
- **AND** both the stable UI and Textual TUI SHALL be able to start with a
  readable theme from that value

#### Scenario: User selects a Textual-only TUI theme
- **WHEN** the user selects a supported Textual-only theme in the Textual TUI
- **THEN** Deepy SHALL persist the selected Textual theme in a TUI-specific
  config field
- **AND** it SHALL preserve the shared `ui.theme` value for stable UI
  compatibility

### Requirement: Stable UX Semantics For Textual Redesign
The redesigned Textual TUI SHALL preserve the stable terminal UI's core user
experience semantics where those semantics define everyday Deepy behavior.

#### Scenario: Prompt keyboard semantics are preserved
- **WHEN** a user moves from the stable UI to the redesigned Textual TUI
- **THEN** Enter SHALL submit the prompt
- **AND** Ctrl+J SHALL insert a newline
- **AND** Esc SHALL remain available for interruption or prompt-local escape
  behavior

#### Scenario: Command semantics are preserved
- **WHEN** a user invokes slash commands that are supported by both surfaces
- **THEN** the redesigned Textual TUI SHALL preserve the stable UI's command
  behavior, confirmations, and error semantics unless the change explicitly
  documents a Textual-specific interaction form

#### Scenario: Runtime summary semantics are preserved
- **WHEN** the Textual TUI shows running status, usage, context pressure,
  compact-next state, or exit summaries
- **THEN** the displayed meaning SHALL match the stable UI behavior
- **AND** Textual-specific layout SHALL NOT change the underlying status
  semantics

### Requirement: Stable UI Retirement Preparation
Deepy SHALL treat the redesigned Textual TUI as preparation for a future stable
UI retirement without removing the stable UI in this change.

#### Scenario: New Textual behavior is implemented
- **WHEN** implementation adds redesigned Textual behavior
- **THEN** the behavior SHALL be tested in the Textual surface
- **AND** implementation SHOULD avoid adding duplicate stable/TUI code paths
  unless needed to preserve existing stable UI behavior during the migration

#### Scenario: Future stable UI removal is considered
- **WHEN** maintainers evaluate a later change to make Textual the default and
  remove the stable UI
- **THEN** they SHALL verify Textual input reliability, command coverage,
  transcript rendering, approvals, sessions, skills, status, background tasks,
  documentation, and cross-terminal behavior before removing the stable UI

### Requirement: Classic UI source package

The default prompt-toolkit terminal UI SHALL live under `deepy.ui.classic` and share
primitives through `deepy.ui.shared`.

#### Scenario: Maintainer imports the classic terminal loop

- **WHEN** code loads the default interactive UI
- **THEN** it SHALL import from `deepy.ui.classic` (for example
  `deepy.ui.classic.terminal`)
- **AND** shared rendering, session, and input helpers SHALL be imported from
  `deepy.ui.shared` rather than duplicating them under `deepy.ui.classic`

#### Scenario: Package boundary exports stable entry points

- **WHEN** external code imports `deepy.ui`
- **THEN** it SHALL be able to reach `run_interactive` and `run_tui` without
  importing removed top-level UI modules such as `deepy.ui.terminal` or `deepy.tui`

