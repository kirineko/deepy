# experimental-textual-tui Specification

## Purpose
TBD - created by archiving change add-experimental-textual-tui. Update Purpose after archive.
## Requirements
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
- **THEN** it SHALL show the Deepy identity, current project root, active provider,
  active model, thinking mode, session state, and experimental status
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
- **WHEN** a user presses Ctrl+J while editing the prompt
- **THEN** the TUI SHALL insert a newline into the prompt
- **AND** it SHALL NOT submit the prompt

#### Scenario: User clears draft with Esc then timely delete
- **WHEN** a user is editing a non-empty Textual TUI prompt
- **AND** the user presses Esc followed by Delete or Backspace within 2 seconds
- **THEN** the TUI SHALL clear the entire prompt draft
- **AND** it SHALL refresh prompt-adjacent suggestion surfaces for the empty
  draft
- **AND** a single Delete or Backspace without the preceding Esc SHALL keep the
  normal character deletion behavior

#### Scenario: Esc delete shortcut expires
- **WHEN** a user presses Esc while editing a non-empty Textual TUI prompt
- **AND** more than 2 seconds elapse before the user presses Delete or Backspace
- **THEN** the TUI SHALL keep the normal character deletion behavior
- **AND** it SHALL NOT clear the entire prompt draft

#### Scenario: User opens slash command discovery
- **WHEN** a user types `/` at the beginning of the prompt
- **THEN** the TUI SHALL expose available Deepy slash commands in a selectable
  Textual surface

#### Scenario: User references project files
- **WHEN** a user starts a file mention with `@`
- **THEN** the TUI SHALL provide a project-file mention affordance
- **AND** selected file mentions SHALL be inserted into the prompt text

#### Scenario: Textual short file mention fragment searches nested paths
- **WHEN** a user types a short non-empty Textual TUI `@` fragment without a
  directory separator
- **THEN** the TUI SHALL include matching nested files and directories from the
  active project root in the completion candidates
- **AND** the search SHALL remain bounded by the same candidate limit, cache,
  ignore rules, symlink exclusions, and project-root containment rules used by
  file mention discovery
- **AND** bare `@` SHALL remain limited to top-level project candidates

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

#### Scenario: Model command is implemented in TUI
- **WHEN** a user invokes `/model` or `/reset` in the experimental TUI
- **THEN** the TUI SHALL use Textual-native provider, model, and thinking selection surfaces
- **AND** it SHALL NOT fall back to the stable prompt-toolkit picker

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

### Requirement: Textual Input Suggestion Ghost Text
The experimental Textual TUI SHALL provide input suggestion ghost text that
matches the stable UI semantics as closely as Textual permits.

#### Scenario: Suggestion becomes visible in Textual prompt
- **WHEN** an eligible input suggestion is available
- **AND** the Textual prompt input buffer is empty
- **THEN** the TUI SHALL render the suggestion in the prompt area as muted
  ghost text
- **AND** the ghost text SHALL NOT be rendered as a slash-command or file-mention
  dropdown entry

#### Scenario: Textual user accepts with Tab
- **WHEN** ghost-text input suggestion is visible in the Textual TUI
- **AND** the user presses Tab
- **THEN** the TUI SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: Textual user accepts with Right Arrow
- **WHEN** ghost-text input suggestion is visible in the Textual TUI
- **AND** the user presses Right Arrow
- **THEN** the TUI SHALL insert the suggestion into the prompt buffer
- **AND** it SHALL NOT submit the prompt

#### Scenario: Textual user presses Enter with visible suggestion
- **WHEN** ghost-text input suggestion is visible in the Textual TUI
- **AND** the input buffer is empty
- **AND** the user presses Enter
- **THEN** the TUI SHALL NOT insert or submit the suggestion
- **AND** Enter SHALL retain the Textual prompt's existing submit behavior

#### Scenario: Textual prompt has another suggestion surface
- **WHEN** slash command suggestions or file mention suggestions are visible in
  the Textual prompt
- **THEN** those existing suggestion surfaces SHALL retain their selection
  behavior
- **AND** input suggestion ghost text SHALL NOT overlap them incoherently

#### Scenario: Textual ghost rendering is constrained
- **WHEN** Textual `TextArea` internals prevent exact inline ghost-text
  rendering
- **THEN** Deepy SHALL still render the suggestion in the prompt area with ghost
  styling
- **AND** it SHALL preserve the same Tab, Right Arrow, Enter, and dismissal
  semantics

### Requirement: Textual Status View Usage And Balance
The experimental Textual TUI SHALL show the same local usage and DeepSeek balance summary in its `/status` auxiliary view while preserving the stable UI's `/status`-only balance lookup rule.

#### Scenario: User opens Textual status view
- **WHEN** the user invokes `/status` or selects the status command in the experimental Textual TUI
- **THEN** the TUI SHALL open a status view
- **AND** the view SHALL include active model, reasoning mode, current session, theme, loaded skills, session count, skill count, MCP status, and config path
- **AND** the view SHALL include active-session Token Usage when known
- **AND** the view SHALL include project-level Token Usage when known
- **AND** the view SHALL include Context Window occupancy when known
- **AND** the view SHALL include DeepSeek balance status returned for that `/status` invocation

#### Scenario: Textual status view cannot retrieve balance
- **WHEN** the user opens the Textual status view
- **AND** Deepy cannot retrieve DeepSeek balance
- **THEN** the view SHALL still open
- **AND** it SHALL show concise balance unavailable text
- **AND** it SHALL keep local status and usage information visible

#### Scenario: Textual non-status surfaces update
- **WHEN** the Textual TUI updates its status bar, side panel, welcome/help text, model-turn progress, local command progress, input suggestions, or usage blocks
- **THEN** it SHALL NOT call the DeepSeek balance endpoint
- **AND** it SHALL NOT show balance information outside the `/status` auxiliary view

### Requirement: Textual Exit Summary Panel
The experimental Textual TUI SHALL show the redesigned exit summary panel with
local usage and DeepSeek session-cost information when it exits.

#### Scenario: User exits Textual TUI with slash command
- **WHEN** the user runs `/exit` or `/quit` in the experimental Textual TUI
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL show the redesigned exit summary panel after returning to
  the normal terminal
- **AND** it SHALL use the same usage and session-cost summary content as the
  stable terminal UI

#### Scenario: User exits Textual TUI with Ctrl+D
- **WHEN** the user confirms exit with Ctrl+D twice in the experimental Textual
  TUI
- **THEN** Deepy SHALL close the Textual app cleanly
- **AND** it SHALL show the redesigned exit summary panel after returning to
  the normal terminal
- **AND** it SHALL use the same usage and session-cost summary content as the
  stable terminal UI

#### Scenario: Textual session cost cannot be computed
- **WHEN** the experimental Textual TUI exits
- **AND** Deepy cannot compute a reliable DeepSeek session-cost balance delta
- **THEN** the exit summary SHALL still render after returning to the normal
  terminal
- **AND** it SHALL keep local usage summary content visible
- **AND** it SHALL show concise cost unavailable text when cost tracking was
  attempted

### Requirement: Textual Provider Model Selection
The experimental Textual TUI SHALL expose the same provider-aware model and
thinking settings as the stable terminal UI.

#### Scenario: User opens Textual model command without arguments
- **WHEN** a user invokes `/model` in the experimental TUI without arguments
- **THEN** the TUI SHALL present provider choices `DeepSeek`, `OpenRouter`, and `Xiaomi`
- **AND** it SHALL present only models supported by the selected provider
- **AND** it SHALL present only thinking choices supported by the selected provider

#### Scenario: User selects Textual provider model settings
- **WHEN** a user completes provider, model, and thinking selection in the experimental TUI
- **THEN** the TUI SHALL persist the selected settings to TOML
- **AND** it SHALL reload in-memory settings for subsequent model turns
- **AND** it SHALL show a concise confirmation with provider, model, and thinking mode

#### Scenario: User resets config in Textual TUI
- **WHEN** a user invokes `/reset` in the experimental TUI
- **THEN** the reset form SHALL allow selecting provider `DeepSeek`, `OpenRouter`, or `Xiaomi`
- **AND** the model choices SHALL match the selected provider
- **AND** the base URL SHALL default to the selected provider's default base URL
- **AND** the thinking choices SHALL match the selected provider

#### Scenario: User cancels Textual provider selection
- **WHEN** a user cancels provider, model, thinking, or reset selection before saving
- **THEN** the TUI SHALL preserve the existing saved settings
- **AND** it SHALL keep current in-memory settings unchanged

### Requirement: Textual Recoverable Tool Attempt Display
The experimental TUI SHALL show recoverable malformed v3 file-tool attempts
without making the transcript look like a completed failed edit when the model
can safely retry.

#### Scenario: Retryable invalid arguments update a tool block
- **WHEN** the TUI receives a tool output with `error_code="invalid_arguments"`
  and `retryable=true`
- **THEN** it SHALL update the corresponding tool block to a retryable or
  recoverable state
- **AND** the block SHALL remain visually distinct from blocking failed mutation
  states
- **AND** the block SHALL expose the concise recovery detail when details are
  expanded

#### Scenario: Recovered file-tool attempt is folded
- **WHEN** a retryable malformed `Read`, `Write`, or `Update` attempt is
  followed in the same model turn by a successful invocation of the same file
  tool for the same target path or target edit set
- **THEN** the TUI MAY fold the retryable attempt into the successful tool block
- **AND** the visible block SHALL indicate that the operation recovered after an
  argument retry
- **AND** the TUI SHALL NOT remove or rewrite persisted session history

#### Scenario: Blocking failure is not folded
- **WHEN** a `Write` or `Update` attempt fails because of stale or unread
  targets, path policy, unsupported target type, approval policy, guardrails,
  absent matches, ambiguous matches, count mismatches, no-op edits, atomic write
  failure, backup failure, rollback failure, or partial commit
- **THEN** the TUI SHALL render the failure as a blocking failed tool block
- **AND** it SHALL NOT fold the failure into a later successful call unless the
  failure was explicitly marked retryable argument failure metadata

### Requirement: Textual Safe Malformed Argument Summaries
The experimental TUI SHALL summarize malformed v3 file-tool arguments without
rendering large raw mutation payloads in tool blocks or details by default.

#### Scenario: Malformed file-tool call is shown
- **WHEN** the TUI renders a malformed `Read`, `Write`, or `Update` tool call
- **THEN** it SHALL show the normalized tool label and a bounded summary
- **AND** it SHALL include safely extracted target path, target count, or edit
  count hints when available
- **AND** it SHALL NOT show raw large `content`, `old`, `new`, or edit body text
  in the collapsed block

#### Scenario: User expands malformed argument details
- **WHEN** a user expands a malformed v3 file-tool block
- **THEN** the TUI MAY show diagnostic details such as parse error location and
  recovery hint
- **AND** any raw argument text shown in details SHALL be bounded to avoid
  overwhelming the transcript

### Requirement: Textual Background Task Compatibility
The experimental Textual TUI SHALL preserve background task lifecycle guarantees without becoming the primary background task management UI.

#### Scenario: Background task exists in Textual TUI
- **WHEN** a managed background task is running while the experimental TUI is active
- **THEN** the TUI SHALL keep background output out of active thinking, assistant response, and foreground tool blocks
- **AND** it SHALL remain responsive to supported navigation and interrupt actions

#### Scenario: Textual TUI exits with background tasks
- **WHEN** the user exits the experimental TUI while managed background tasks are running
- **THEN** Deepy SHALL stop all running managed background tasks before the Textual app fully exits
- **AND** it SHALL return control to the user's terminal without requiring a separate cleanup command

#### Scenario: Textual command support is not yet implemented
- **WHEN** a user invokes `/ps` or `/stop` in the experimental TUI before Textual-native command handling exists for that command
- **THEN** the TUI SHALL show a clear unsupported-in-TUI message
- **AND** it SHALL NOT silently start a model turn for that slash command

### Requirement: Textual Slash Command Discovery Ranking
The experimental Textual TUI SHALL use the shared Deepy slash command ranking
for prompt-adjacent slash suggestions and command discovery surfaces.

#### Scenario: Bare slash suggestions reveal all command kinds
- **WHEN** a user types `/` at the beginning of the Textual TUI prompt
- **THEN** the TUI SHALL provide selectable suggestions for built-in commands,
  subagent commands, and skill invocation commands
- **AND** subagent and skill suggestions SHALL NOT be hidden solely because the
  first visible rows are occupied by built-in commands
- **AND** the suggestion surface SHALL allow keyboard access to additional
  ranked candidates when more candidates exist than visible rows

#### Scenario: Bare slash suggestions prioritize useful actions
- **WHEN** the Textual TUI displays slash suggestions for a bare `/`
- **THEN** common workflow commands SHALL rank before lower-frequency
  management or exit commands
- **AND** subagent commands SHALL rank before otherwise equivalent unloaded skill
  commands
- **AND** loaded skills SHALL rank ahead of otherwise equivalent unloaded skills

#### Scenario: Typed slash suggestions share stable UI ranking
- **WHEN** a user types a partial slash command token in the Textual TUI prompt
- **THEN** the TUI SHALL rank exact matches before prefix matches
- **AND** it SHALL rank prefix matches before weaker description or substring
  matches
- **AND** it SHALL use the same shared slash command priority tie-breakers as
  the stable UI

#### Scenario: Selecting a suggestion only inserts the command
- **WHEN** a user selects a Textual TUI slash suggestion
- **THEN** the TUI SHALL insert the selected command token into the prompt
- **AND** it SHALL NOT submit the prompt or start a model turn until the user
  submits the prompt explicitly

### Requirement: Textual Sessions Survive Storage Replacement
The experimental Textual TUI SHALL preserve user-facing session behavior while
the underlying active session store changes.

#### Scenario: User resumes a TUI session
- **WHEN** a user selects a session from `/resume` or the sessions surface
- **THEN** the TUI SHALL list and restore sessions from the active transactional
  session store
- **AND** subsequent prompts SHALL continue the selected session id

#### Scenario: TUI restores transcript tail
- **WHEN** the TUI restores visible transcript history for a selected session
- **THEN** it SHALL read the requested recent ordered session items from the
  active transactional session store
- **AND** it SHALL render user, assistant, reasoning, tool call, and tool output
  items using the same conventions as live output

#### Scenario: TUI compacts active session
- **WHEN** a user invokes `/compact` in the experimental TUI with an active
  session
- **THEN** Deepy SHALL run durable session compaction against the active
  transactional session store
- **AND** the active session id SHALL remain usable after compaction succeeds

#### Scenario: TUI local command records transcript
- **WHEN** a TUI local command-mode command completes
- **THEN** Deepy SHALL persist the synthetic shell transcript records in the
  active transactional session store
- **AND** later TUI resume and model replay SHALL see the stored local command
  transcript

### Requirement: Textual Cache Health Display
The experimental Textual TUI SHALL expose cache health using the same normalized
session metadata as the default terminal UI.

#### Scenario: TUI session has cache usage data
- **WHEN** the active Textual TUI session has cache hit and miss token data
- **THEN** the TUI SHALL show cache hit ratio and cached/fresh input token
  information in an appropriate status, footer, detail, or session view
- **AND** it SHALL update that display after model turns complete

#### Scenario: TUI session has unknown cache usage
- **WHEN** the active provider or model turn does not report cache hit and miss
  token data
- **THEN** the TUI SHALL show cache health as unknown or omit the cache metric
- **AND** it SHALL NOT imply a zero percent cache hit ratio

### Requirement: Textual Cache Break Visibility
The experimental Textual TUI SHALL make cache-breaking context changes visible
without depending on provider-specific raw events.

#### Scenario: Cache break is recorded
- **WHEN** Deepy records a cache break from compaction, retry recovery, interrupt
  cleanup, prefix change, or tool-set change
- **THEN** the Textual TUI SHALL make the latest cache-break reason available in
  status, footer, detail, or session views
- **AND** it SHALL consume the normalized Deepy session metadata instead of raw
  provider event objects

#### Scenario: Cache metadata is rendered
- **WHEN** the Textual TUI renders cache health or cache-break information
- **THEN** it SHALL NOT print API keys, authorization headers, or full provider
  payloads

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

### Requirement: Textual Audit Mode Visibility

The experimental Textual TUI SHALL make the active system audit mode visible
during interactive use.

#### Scenario: Status bar shows audit mode

- **WHEN** the Textual TUI is waiting for user input or running a model turn
- **THEN** the status bar SHALL include the active audit mode
- **AND** it SHALL keep existing provider, model, working-directory, MCP,
  background-task, context, and cache status segments readable

#### Scenario: Status screen shows audit mode

- **WHEN** the user opens the Textual TUI status surface such as `/status`
- **THEN** the status screen SHALL include the active audit mode
- **AND** it SHALL distinguish runtime mode from persisted configuration when
  they differ

### Requirement: Textual Audit Mode Cycling

The experimental Textual TUI SHALL support cycling audit modes with the same
runtime mode order as the stable terminal UI.

#### Scenario: User cycles audit mode

- **WHEN** the user presses `Shift+Tab` while the Textual TUI prompt is active
- **THEN** Deepy SHALL switch to the next audit mode in the order `normal`,
  `auto`, `yolo`, `normal`
- **AND** Deepy SHALL update visible Textual status surfaces without submitting
  the current prompt text

#### Scenario: Tab completion remains available

- **WHEN** the user presses `Tab` without `Shift` while the Textual TUI prompt is active
- **THEN** Deepy SHALL preserve existing slash-command completion, file-mention,
  and input-suggestion behavior
- **AND** it SHALL NOT cycle the audit mode

### Requirement: Textual Approval Prompt Display

The experimental Textual TUI SHALL present SDK approval interruptions as
explicit Textual approval prompts rather than normal assistant questions.

#### Scenario: Built-in tool approval prompt is displayed

- **WHEN** an SDK run pauses for approval of a built-in side-effect tool in the Textual TUI
- **THEN** the TUI SHALL render a Textual approval prompt that identifies the
  action kind, tool name, arguments summary, and relevant target command, path,
  or task id
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: MCP approval prompt is displayed

- **WHEN** an SDK run pauses for approval of an MCP tool call in the Textual TUI
- **THEN** the TUI SHALL render a Textual approval prompt that identifies the MCP
  server, MCP tool, and arguments summary
- **AND** the user SHALL be able to approve or reject the action

#### Scenario: Approval prompt is not transcript noise

- **WHEN** the Textual TUI renders an approval prompt
- **THEN** it SHALL distinguish the prompt from model-authored `AskUserQuestion`
  content
- **AND** it SHALL NOT append the approval prompt text as a normal transcript
  message
- **AND** it SHALL NOT submit the approval prompt text as a normal user message

#### Scenario: Rejected approval resumes the turn

- **WHEN** the user rejects an approval prompt in the Textual TUI
- **THEN** Deepy SHALL resume the paused SDK run with a rejection result
- **AND** the TUI SHALL continue rendering subsequent assistant output from the
  resumed run

### Requirement: Textual Task-Focused Audit Approval Panels

The experimental Textual TUI SHALL render audit approval prompts with the same
task-focused summary rules as the stable terminal UI.

#### Scenario: Shell command approval uses task summary

- **WHEN** an SDK approval interruption requests a shell command execution in the Textual TUI
- **THEN** Deepy SHALL show a title that identifies the request as a shell
  command approval
- **AND** it SHALL show the command as the primary target
- **AND** it SHALL show meaningful secondary context such as description or
  working directory when available
- **AND** it SHALL NOT show raw internal field labels such as `action`, `agent`,
  or `arguments.*` unless no typed summary can be derived

#### Scenario: MCP approval uses server and tool summary

- **WHEN** an SDK approval interruption requests an MCP tool call in the Textual TUI
- **THEN** Deepy SHALL show a title that identifies the request as an MCP tool
  approval
- **AND** it SHALL show the MCP server and tool as the primary target
- **AND** it SHALL show only the most relevant bounded argument fields, such as
  `url`, `urls`, `query`, or `format`, when available
- **AND** it SHALL NOT render the full raw argument JSON by default

#### Scenario: Unknown approval falls back to bounded summary

- **WHEN** an SDK approval interruption cannot be classified as shell, file
  mutation, or MCP in the Textual TUI
- **THEN** Deepy SHALL show the tool name and a bounded structured argument
  summary
- **AND** the fallback summary SHALL remain visually distinct from normal
  assistant messages

### Requirement: Textual File Mutation Approval Diff Review

The experimental Textual TUI SHALL render `Write` and `Update` audit approvals
with diff previews and relative target paths when possible.

#### Scenario: Write approval shows new-file diff

- **WHEN** an SDK approval interruption requests writing content to a file under
  the active project root in the Textual TUI
- **THEN** Deepy SHALL display the file path relative to the project root
- **AND** it SHALL show a diff preview representing the proposed new file content
- **AND** it SHALL keep the final decision area limited to `Approve` and `Reject`

#### Scenario: Update approval shows changed lines

- **WHEN** an SDK approval interruption requests updating content in a file in
  the Textual TUI
- **AND** the approval arguments contain enough before-and-after information to
  derive a diff
- **THEN** Deepy SHALL display the file path relative to the project root when
  the file is under that root
- **AND** it SHALL show a diff preview that includes removed and added lines

#### Scenario: File path outside project remains explicit

- **WHEN** an SDK approval interruption targets a file outside the active project
  root in the Textual TUI
- **THEN** Deepy SHALL NOT display the path as project-relative
- **AND** it SHALL display a home-relative path when possible or the absolute
  path otherwise

#### Scenario: Long diff preview uses scrolling without extra decision controls

- **WHEN** a `Write` or `Update` diff preview exceeds the compact preview budget
  in the Textual TUI
- **THEN** Deepy SHALL render the diff preview in a bounded scrollable Textual
  region
- **AND** it SHALL keep the decision controls limited to `Approve` and `Reject`

#### Scenario: Missing update diff context uses safe fallback

- **WHEN** an `Update` approval in the Textual TUI does not contain enough
  before-and-after information to derive a reliable diff
- **THEN** Deepy SHALL show a compact typed summary instead of fabricating a diff
- **AND** it SHALL still display the target path using the relative-path rules

### Requirement: Textual Approval Prompt Keyboard Interaction

The experimental Textual TUI approval prompt SHALL resolve approvals only through
navigation selection, `Enter`, and `Esc`.

#### Scenario: Arrow keys move selection

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Up` or `Down`
- **THEN** Deepy SHALL move the selection among visible approval decision controls
- **AND** it SHALL NOT approve or reject the tool call only because selection
  moved

#### Scenario: Enter activates selected control

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Enter`
- **AND** the selected control is `Approve` or `Reject`
- **THEN** Deepy SHALL resolve the SDK approval with the selected decision

#### Scenario: Escape rejects approval

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Esc`
- **THEN** Deepy SHALL resolve the SDK approval as rejected

#### Scenario: Letter shortcuts do not resolve approval

- **WHEN** an approval prompt is active in the Textual TUI
- **AND** the user presses `Y`, `A`, `N`, `R`, or their lowercase equivalents
- **THEN** Deepy SHALL NOT resolve the SDK approval because of that keypress
- **AND** visible approval hints SHALL NOT advertise those letter shortcuts

### Requirement: Textual TUI Image Paste Attachments
The experimental Textual TUI SHALL support the same image attachment contract as the stable terminal UI.

#### Scenario: User pastes image into supported Textual prompt
- **WHEN** the Textual TUI prompt has focus
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model supports image input
- **THEN** the TUI SHALL attach the image to the current prompt draft
- **AND** it SHALL insert the attachment label into the prompt input text as `[图片1]`, `[图片2]`, or the next available image label
- **AND** it SHALL preserve existing prompt text and cursor-editing behavior

#### Scenario: User deletes image label from Textual prompt input
- **WHEN** a Textual TUI prompt draft contains an inserted image label
- **AND** the user deletes that label from the prompt text before submission
- **THEN** the TUI SHALL remove the corresponding image attachment from the draft
- **AND** it SHALL NOT send that image with the next prompt submission

#### Scenario: User deletes within image label from Textual prompt input
- **WHEN** a Textual TUI prompt draft contains an inserted image label
- **AND** the cursor is inside the label or immediately after the label
- **AND** the user presses Backspace
- **THEN** the TUI SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft
- **WHEN** the cursor is inside the label or immediately before the label
- **AND** the user presses Delete
- **THEN** the TUI SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft

#### Scenario: User pastes image into unsupported Textual prompt
- **WHEN** the Textual TUI prompt has focus
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model does not support image input
- **THEN** the TUI SHALL append a concise assistant-visible message to the transcript
- **AND** it SHALL NOT show the rejection only in the status/footer bar
- **AND** it SHALL discard the pasted image
- **AND** it SHALL preserve the current prompt text
- **AND** it SHALL keep accepting text input

#### Scenario: User submits Textual prompt with images
- **WHEN** a Textual TUI prompt draft contains text and image attachments
- **AND** the user presses Enter
- **THEN** the TUI SHALL submit the text and image attachments as one user turn
- **AND** the displayed user transcript block SHALL include the prompt text and compact image labels
- **AND** it SHALL NOT display raw base64 data

#### Scenario: Textual prompt remains responsive after image rejection
- **WHEN** an image paste is rejected because the model, MIME type, size, or clipboard adapter is unsupported
- **THEN** the Textual TUI SHALL keep the prompt focused and editable
- **AND** it SHALL preserve the current prompt text

### Requirement: Textual Diff Syntax Highlighting Consistency
The experimental Textual TUI SHALL render Deepy-owned diff blocks with the same
XML-family syntax highlighting guarantees as the stable terminal diff renderer.

#### Scenario: TUI diff preserves multiline XML syntax
- **WHEN** the experimental Textual TUI renders a `Write` or `Update` diff block
  for XML content with multiline tags, attributes, comments, or CDATA
- **THEN** the TUI SHALL preserve XML syntax highlighting across the related
  diff lines
- **AND** the diff block SHALL keep readable added and removed line colors,
  gutters, markers, hunk navigation data, and truncation behavior

#### Scenario: TUI diff recognizes XML-like files
- **WHEN** the experimental Textual TUI renders a diff block for a recognized
  XML-family file type such as SVG, XAML, C# project files, MSBuild props or
  targets files, or well-known XML-based config files
- **THEN** the TUI SHALL use XML syntax highlighting instead of falling back to
  unhighlighted plain text

#### Scenario: TUI non-XML diff highlighting is preserved
- **WHEN** the experimental Textual TUI renders diff blocks for already
  supported mainstream languages such as Python, JavaScript, TypeScript, TSX,
  JSON, YAML, TOML, Rust, CSS, shell, or SQL
- **THEN** the TUI SHALL preserve existing syntax highlighting behavior
- **AND** unsupported or unknown languages SHALL continue to fall back to
  readable plain text rather than failing rendering

### Requirement: Modern UI Blocking Interactions
Modern UI SHALL keep bottom-sheet decision flows keyboard-completable even when
the transcript or prompt attempts to regain focus.

#### Scenario: Audit decision owns keyboard focus
- **WHEN** an audit approval decision is pending in Modern UI
- **AND** the prompt would otherwise receive focus or an `Esc` key
- **THEN** the pending audit decision SHALL keep keyboard ownership
- **AND** `Esc` SHALL reject the pending audit decision
- **AND** the prompt SHALL NOT consume keys that leave the audit decision
  unresolved

#### Scenario: Ask-user-question owns keyboard focus
- **WHEN** an ask-user-question response is pending in Modern UI
- **AND** the prompt would otherwise receive focus or an `Esc` key
- **THEN** the pending question flow SHALL keep keyboard ownership
- **AND** `Esc` SHALL cancel or decline the pending question flow
- **AND** the prompt SHALL NOT consume keys that leave the question unresolved

### Requirement: Modern UI Diff Ordering And Scrolling
Modern UI SHALL render file mutation diffs in chronological transcript order
without breaking conversation scrolling.

#### Scenario: Diff replaces compact mutation output
- **WHEN** a `Write` or `Update` tool output contains diff metadata
- **THEN** Modern UI SHALL render the diff block at the tool output position
- **AND** it SHALL NOT leave a separate compact output row for the same mutation
- **AND** later tool outputs SHALL remain after the diff block

#### Scenario: Diff precedes streamed mutation summary
- **WHEN** Modern UI has already rendered streamed assistant text in the current
  turn
- **AND** a later `Write` or `Update` tool output contains diff metadata
- **THEN** Modern UI SHALL place the diff block before the current assistant
  text block
- **AND** it SHALL NOT duplicate the compact mutation output row

#### Scenario: Large diff remains scroll-safe
- **WHEN** a rendered diff is larger than the visible transcript region
- **THEN** Modern UI SHALL keep transcript scrolling functional
- **AND** prompt history navigation SHALL NOT be the only available scroll
  behavior

### Requirement: Modern UI Composer Ergonomics
Modern UI SHALL provide a fixed-height multi-line composer that remains usable
for longer prompts.

#### Scenario: Composer has four visible prompt lines
- **WHEN** Modern UI is idle
- **THEN** the prompt composer SHALL reserve four visible input lines
- **AND** status, attachment, and hint rows SHALL remain visible without overlap
- **AND** the prompt composer SHALL NOT resize between one and five lines as the
  draft changes

#### Scenario: Long draft scrolls inside composer
- **WHEN** the prompt draft exceeds four visible lines
- **THEN** the prompt input SHALL allow the user to scroll or navigate within
  the draft
- **AND** it SHALL NOT expand in a way that hides the transcript or status bar

### Requirement: Modern UI Dense Markdown Output
Modern UI SHALL render Markdown tables and adjacent transcript blocks with
terminal-appropriate density.

#### Scenario: Table output is compact
- **WHEN** assistant or tool output contains a Markdown table
- **THEN** Modern UI SHALL render the table without excessive vertical padding
- **AND** table rows SHALL remain visually connected to adjacent table rows
- **AND** surrounding transcript spacing SHALL remain compact and readable

#### Scenario: Table output preserves autoscroll
- **WHEN** the Modern UI transcript is anchored at the bottom
- **AND** assistant output updates to Markdown that includes a table large enough
  to change the transcript height
- **THEN** Modern UI SHALL remain scrolled to the bottom after the Markdown table
  finishes rendering

### Requirement: Modern UI Proposed File Changes
Modern UI SHALL render preflighted file mutation diffs in the transcript before
asking for a normal-mode approval decision.

#### Scenario: Proposed diff appears before file approval
- **WHEN** a normal-mode `Write` or `Update` approval requires a preflight diff
- **THEN** Modern UI SHALL append a proposed file change block to the transcript
- **AND** it SHALL show the approval decision in the bottom interaction sheet
- **AND** the decision sheet SHALL NOT contain the large diff preview

#### Scenario: Proposed diff records rejection
- **WHEN** the user rejects a proposed file mutation in Modern UI
- **THEN** the proposed change block SHALL remain in the transcript
- **AND** it SHALL show a rejected state

### Requirement: Modern UI shall render command-mode local command results without unnecessary noise

The Modern UI MUST render `!cmd` results in the transcript without calling the
model, and successful commands MUST NOT display a redundant `exit 0` metadata
line. Failed commands MUST still expose their non-zero exit code.

#### Scenario: Successful local command hides exit-zero metadata

- **GIVEN** a user submits `!pwd`
- **WHEN** the command exits with code `0`
- **THEN** the Modern UI transcript shows the command output
- **AND** the local command metadata does not include `exit 0`

#### Scenario: Failed local command keeps non-zero exit metadata

- **GIVEN** a user submits a local command that exits with code `2`
- **WHEN** the result is rendered in Modern UI
- **THEN** the transcript metadata includes `exit 2`

### Requirement: Modern UI shall keep bottom-sheet picker options readable

The Modern UI MUST make bottom-sheet `OptionList` choices readable across
supported Textual themes, including provider, model, theme, audit, and
ask-user-question flows.

#### Scenario: Inline picker options remain visible

- **GIVEN** a bottom-sheet picker is opened for provider/model style selection
- **WHEN** options are mounted
- **THEN** option text, highlighted option text, and disabled option text have
  explicit readable styles
- **AND** the option list is not visually blank.

#### Scenario: Inline command picker returns stable option values

- **GIVEN** a user submits `/ui` without an argument
- **WHEN** the user selects the Classic UI option from the bottom-sheet picker
- **THEN** the Modern UI persists `classic` as the configured UI interface
- **AND** the transcript does not show a `/ui classic|modern` usage error.

### Requirement: Modern UI Surface Polish
The Modern UI SHALL keep conversation transcript content separate from transient interaction controls and SHALL present management surfaces with compact, readable layouts.

#### Scenario: Classic and Modern UI are peer system UIs
- **WHEN** Deepy describes terminal UI choices
- **THEN** the Rich/prompt-toolkit UI SHALL be called `Classic UI`
- **AND** the Textual UI SHALL be called `Modern UI`
- **AND** Modern UI SHALL NOT be described as experimental

#### Scenario: Light theme resolves to Solarized Light
- **WHEN** the Modern UI starts with the shared `light` UI theme and no explicit Textual theme override
- **THEN** it SHALL use `solarized-light` as the Textual theme

#### Scenario: Prompt footer shows concise interrupt hint
- **WHEN** the prompt action hint is rendered
- **THEN** it SHALL show `Esc interrupt`
- **AND** it SHALL NOT show `Ctrl+C interrupt`

#### Scenario: Transcript content is copyable
- **WHEN** conversation content is rendered in the transcript
- **THEN** the TUI SHALL preserve terminal-native copy affordances where the terminal and Textual configuration permit them
- **AND** it SHALL bind `Ctrl+C` and `Cmd+C`/`super+c` to an app-level transcript copy action
- **AND** the copy action SHALL copy the currently focused transcript block when Textual receives the key event
- **AND** it SHALL NOT use `Ctrl+C` as the Modern UI interrupt action

#### Scenario: Reasoning transcript uses compact styling
- **WHEN** reasoning or thinking content is shown in the transcript
- **THEN** it SHALL use the same compact role-line layout as other transcript blocks
- **AND** it SHALL avoid rendering a large standalone `Thinking` title

#### Scenario: Choices use bottom interaction sheet
- **WHEN** the user opens a transient choice flow such as theme, model, session, audit, or ask-user-question selection
- **THEN** the choice controls SHALL appear in a bottom interaction surface near the prompt
- **AND** selecting or cancelling the choice SHALL NOT append decision-result text to the transcript

#### Scenario: Skill management uses compact differentiated rows
- **WHEN** the user opens the skill management surface
- **THEN** installed and market tabs SHALL be visibly presented as tabs
- **AND** each skill SHALL render as a single row with name, state/source metadata, and a truncated description
- **AND** skill rows SHALL keep long descriptions on one visual line by truncating overflow
- **AND** skill rows SHALL use the available management surface width before truncating descriptions
- **AND** installed, market, built-in, and updateable states SHALL be visually distinguishable
- **AND** market rows SHALL show installed state without showing version numbers
- **AND** installed rows SHALL show whether each skill is installed in user or project scope

#### Scenario: Skill market loading is asynchronous
- **WHEN** the user opens or refreshes the skill management surface
- **THEN** the surface SHALL appear immediately with a loading state while market HTTP data is fetched
- **AND** the TUI SHALL update the existing surface when market data or errors are available
- **WHEN** the user installs or uninstalls a skill from the skill management surface
- **THEN** the surface SHALL show an operation loading state while the action is running
- **AND** the surface SHALL refresh in place after the action completes

#### Scenario: Skill management actions stay in the management flow
- **WHEN** the user installs or uninstalls a skill from the skill management surface
- **THEN** the TUI SHALL refresh the skill management surface
- **AND** it SHALL NOT append install or uninstall result text to the transcript
- **WHEN** the user presses Enter on an uninstalled market skill
- **THEN** the TUI SHALL show skill detail
- **WHEN** the user presses `i` on an uninstalled market skill
- **THEN** the TUI SHALL ask for the install scope before installing
- **WHEN** the user presses Enter or `v` on an installed skill row
- **THEN** the TUI SHALL show skill detail instead of loading the skill into the conversation

#### Scenario: Status and configuration information is grouped
- **WHEN** the user opens status or configuration information from the Modern UI
- **THEN** the information SHALL be grouped into concise sections for model, runtime, project, MCP, session, and UI where applicable
- **AND** it SHALL avoid dumping broad mixed markdown when compact grouped data is available

#### Scenario: MCP command prints current runtime tools
- **WHEN** the user runs `/mcp` in Modern UI
- **THEN** the TUI SHALL append the current MCP server and tool status to the transcript
- **AND** it SHALL use the same MCP status formatter as Classic UI
- **AND** it SHALL NOT open an MCP configuration modal

#### Scenario: Local command output is visible
- **WHEN** the user submits a local command with `!<command>` in Modern UI
- **THEN** the TUI SHALL append the command result to the transcript as a visible shell output block
- **AND** the block SHALL show the command output without requiring an expand action
- **AND** the block SHALL include concise execution metadata such as exit status and duration
- **AND** regular model tool calls SHALL remain compact unless they are user local command results

### Requirement: Configured UI Routing
Deepy SHALL persist the default system UI and route the default interactive command through that setting.

#### Scenario: Missing UI config defaults to Classic dark
- **WHEN** no UI interface or theme is configured
- **THEN** Deepy SHALL default to `classic` interface and `dark` theme

#### Scenario: Default command uses configured UI
- **WHEN** the user starts `deepy`
- **THEN** Deepy SHALL start Classic UI when `ui.interface` is `classic`
- **AND** Deepy SHALL start Modern UI when `ui.interface` is `modern`
- **AND** `deepy tui` SHALL remain available as a Modern UI compatibility command

#### Scenario: Slash command persists UI choice
- **WHEN** the user runs `/ui classic` or `/ui modern`
- **THEN** Deepy SHALL persist the selected `ui.interface`
- **AND** it SHALL tell the user that the selected UI applies on restart

#### Scenario: Reset setup offers UI and theme combinations
- **WHEN** the user resets or interactively sets up config
- **THEN** the UI selection SHALL offer Classic UI + dark theme, Classic UI + light theme, Modern UI + dark theme, and Modern UI + light theme
- **AND** the first option SHALL be Classic UI + dark theme

### Requirement: Ghostty CJK Input Compatibility
The experimental Textual TUI SHALL prevent Ghostty-specific Kitty keyboard protocol associated-text sequences from being inserted as literal prompt text during CJK IME input.

#### Scenario: Ghostty commits CJK text through associated-text keyboard protocol
- **WHEN** a user starts `deepy tui` in an environment where the terminal would otherwise emit Kitty keyboard protocol associated-text sequences for CJK IME commits
- **THEN** Deepy SHALL configure Textual startup before Textual is imported so the incompatible enhanced keyboard protocol path is disabled by default
- **AND** CJK prompt input SHALL be accepted through normal Textual text input rather than prompt-content replacement after insertion

#### Scenario: User explicitly opts into Textual Kitty keyboard protocol
- **WHEN** the user starts `deepy tui` with a preconfigured Textual keyboard-protocol environment override
- **THEN** Deepy SHALL preserve that explicit environment value
- **AND** it SHALL NOT overwrite the user's selected Textual keyboard protocol behavior

### Requirement: Textual Transcript Experience Redesign
The experimental Textual TUI SHALL render the entire transcript area as a
concise, high-density, visually polished reading surface while preserving access
to detailed content.

#### Scenario: Transcript renders role identity
- **WHEN** the TUI renders user and assistant turns
- **THEN** it SHALL show user and assistant identity in a compact and scannable
  form without requiring literal `You` and `Deepy` labels
- **AND** short turns SHALL NOT require large headers, large cards, or repeated
  blank vertical space
- **AND** user and assistant role markers SHALL be visually distinct and appear
  inline with the first content line instead of occupying their own line

#### Scenario: Transcript uses rail or gutter styling
- **WHEN** the transcript uses a left rail, stripe, gutter, or equivalent
  semantic marker
- **THEN** the marker SHALL be visually lightweight and theme-aware
- **AND** it SHALL support scanning content type and active focus without
  dominating the transcript or creating excessive line chrome

#### Scenario: Assistant Markdown is rendered
- **WHEN** assistant output contains Markdown paragraphs, headings, lists, code
  blocks, tables, links, or inline emphasis
- **THEN** the TUI SHALL render Markdown with dense but readable spacing,
  wrapping, and visual hierarchy
- **AND** paragraphs, bullets, and code blocks SHALL NOT inherit unnecessary
  vertical padding that makes long replies feel sparse
- **AND** code blocks and tables SHALL remain readable and distinguishable from
  prose

#### Scenario: Transcript contains usage and metadata
- **WHEN** a model turn completes with usage, cache, context, or session
  metadata
- **THEN** the TUI SHALL NOT append per-turn usage lines to the transcript
- **AND** it SHALL keep token/cache/context metadata out of the persistent
  status footer unless the user explicitly requests a status or detail view
- **AND** it SHALL NOT add a full-height transcript block for every low-value
  metadata line unless the user expands details

#### Scenario: Transcript contains tool, reasoning, diff, error, and question content
- **WHEN** mixed content appears in the transcript
- **THEN** each content type SHALL remain visually distinguishable by semantic
  label, tone, and state
- **AND** low-value arguments or verbose details SHALL be folded by default when
  a concise summary is available
- **AND** users SHALL be able to expand folded details without losing transcript
  position

#### Scenario: Tool calls render compactly
- **WHEN** the TUI renders tool call or tool result blocks
- **THEN** it SHALL render the visible transcript entry as a compact single-line
  summary aligned with user and assistant turn marker styling
- **AND** it SHALL NOT show tool parameters or output bodies by default in the
  transcript
- **AND** it MAY keep parameters, output, and diagnostic details internally for
  status transitions, recovery, or future explicit detail surfaces

#### Scenario: File edit tools render diff results directly
- **WHEN** `Write` or `Update` succeeds and returns a diff
- **THEN** the TUI SHALL render the diff result directly without an additional
  `Write ok`, `Update ok`, or visible `Diff` label line
- **AND** the diff SHALL appear after the assistant text that led to the tool
  result
- **AND** file paths under the current project root SHALL render as relative
  paths

#### Scenario: Assistant output turns are visually separated
- **WHEN** assistant output or a file edit diff completes
- **THEN** the TUI SHALL provide subtle spacing or separation before the next
  transcript turn

#### Scenario: Transcript is visually reviewed
- **WHEN** the redesigned transcript is validated
- **THEN** long assistant replies, short user prompts, tool summaries, diffs,
  errors, usage metadata, and inline decisions SHALL appear as one coherent
  visual system
- **AND** the result SHALL be simpler, denser, and more polished than the
  previous block-and-left-rail layout

### Requirement: Textual Theme Mapping
The experimental Textual TUI SHALL use Textual's theme system while preserving
Deepy's shared `dark` and `light` UI configuration contract.

#### Scenario: Saved UI theme is dark
- **WHEN** the saved Deepy UI theme is `dark`
- **THEN** the TUI SHALL apply `tokyo-night` as the curated dark Textual theme
- **AND** transcript text, composer text, suggestions, decisions, diffs, and
  status surfaces SHALL remain readable

#### Scenario: Saved UI theme is light
- **WHEN** the saved Deepy UI theme is `light`
- **THEN** the TUI SHALL apply a curated light Textual theme
- **AND** transcript text, composer text, suggestions, decisions, diffs, and
  status surfaces SHALL remain readable

#### Scenario: User previews or selects a Textual theme
- **WHEN** the TUI exposes Textual built-in themes to the user
- **THEN** it SHALL clearly distinguish shared Deepy themes from TUI-specific
  Textual themes
- **AND** it SHALL NOT require the stable UI to understand Textual-only theme
  names
- **AND** it SHALL provide multiple curated Textual theme options in the TUI
  theme picker
- **AND** choosing a Textual-only theme SHALL persist it in a TUI-specific
  setting rather than overloading the shared `ui.theme` value

#### Scenario: Theme changes during a TUI session
- **WHEN** the user changes the TUI theme
- **THEN** the TUI SHALL refresh visible Textual surfaces without requiring an
  immediate app restart
- **AND** persisted settings SHALL remain valid after restarting Deepy

### Requirement: Textual Composer Attachment Management
The experimental Textual TUI SHALL let users inspect and remove image
attachments from the composer before submitting a prompt.

#### Scenario: User attaches images
- **WHEN** one or more images are attached in the composer
- **THEN** the TUI SHALL show each attachment outside the editable prompt text
  as a compact removable attachment item
- **AND** the editable prompt buffer SHALL NOT contain UI-only image label
  tokens
- **AND** the attachment row SHALL explain the keyboard deletion action instead
  of relying on a literal `x` marker that cannot be directly clicked

#### Scenario: User removes an attachment
- **WHEN** the user focuses or selects an attachment item and activates the
  remove action
- **THEN** the TUI SHALL remove only that attachment from the pending submission
- **AND** it SHALL keep the prompt text unchanged
- **AND** it SHALL refresh the composer attachment display

#### Scenario: User removes an attachment while typing
- **WHEN** the editable prompt input has focus and one or more image attachments
  are pending
- **THEN** the user SHALL be able to select attachments with prompt-local
  keyboard shortcuts, including Down
- **AND** after entering attachment selection, Left and Right SHALL move the
  selected attachment
- **AND** Up SHALL leave attachment selection and return to ordinary prompt
  input behavior
- **AND** the user SHALL be able to remove the selected attachment with
  Backspace after an attachment is selected, without leaving the prompt input
- **AND** removal SHALL NOT alter the editable prompt text
- **AND** Backspace SHALL continue to edit prompt text when no attachment is
  explicitly selected

#### Scenario: User submits prompt after removing attachments
- **WHEN** the user submits a prompt after removing one or more attachments
- **THEN** the runner SHALL receive exactly the remaining attachments
- **AND** removed attachments SHALL NOT be included in the submission payload

### Requirement: Textual Live Activity Feedback
The experimental Textual TUI SHALL provide subtle live activity feedback during
long assistant replies, tool execution, and off-bottom transcript updates.

#### Scenario: Assistant reply is streaming
- **WHEN** the assistant block is actively receiving output
- **THEN** the TUI SHALL show a visible live state such as a streaming cursor,
  pulse, or activity marker
- **AND** the live state SHALL update without obscuring assistant content

#### Scenario: Tool call is running
- **WHEN** a tool call has started and has not completed
- **THEN** the corresponding tool block or status surface SHALL visibly indicate
  running state
- **AND** the indication SHALL change when the tool succeeds, fails, waits for
  user input, or becomes retryable

#### Scenario: User has scrolled away from bottom
- **WHEN** new output arrives while the transcript is not anchored at the bottom
- **THEN** the TUI SHALL preserve the user's scroll position
- **AND** it SHALL show an animated or otherwise changing new-output indicator
  until the user returns to the newest output or acknowledges it

#### Scenario: Tests run in headless mode
- **WHEN** TUI tests run in a deterministic headless environment
- **THEN** live activity effects SHALL be reducible or deterministic enough to
  avoid timing-flaky tests

### Requirement: Textual Inline Decision Flow
The experimental Textual TUI SHALL handle frequent user decisions inside the
conversation transcript instead of interrupting the flow with blocking modal
screens.

#### Scenario: TUI interaction is designed
- **WHEN** a TUI interaction surface is added or redesigned
- **THEN** it SHALL prefer preserving transcript information flow and the main
  conversation workflow
- **AND** it SHALL use an inline transcript block, composer-adjacent surface,
  side/detail surface, or other non-disruptive placement unless a separate
  management surface is clearly justified

#### Scenario: Audit approval is requested
- **WHEN** a model turn requires audit approval for a tool action
- **THEN** the TUI SHALL render an inline audit decision block in the transcript
- **AND** the block SHALL show the approval summary, target, relevant metadata,
  and available preview or diff detail
- **AND** the user SHALL be able to approve or reject by keyboard without
  leaving the conversation context

#### Scenario: Audit decision completes
- **WHEN** the user approves or rejects an inline audit decision
- **THEN** the block SHALL update to a completed state that records the selected
  decision
- **AND** the model turn SHALL continue or reject the tool using the same audit
  semantics as before

#### Scenario: AskUserQuestion is returned
- **WHEN** a model turn returns pending AskUserQuestion questions
- **THEN** the TUI SHALL render inline question decision blocks in the transcript
- **AND** those blocks SHALL support single-select, multi-select, custom answer,
  cancellation, and same-session continuation

#### Scenario: Decision is pending
- **WHEN** an inline decision block is waiting for user input
- **THEN** focus SHALL move to that block
- **AND** the composer SHALL make the pending decision state clear
- **AND** normal transcript navigation SHALL remain available

#### Scenario: Existing modal interaction is retained
- **WHEN** an existing modal or screen interaction remains after this redesign
- **THEN** it SHALL have an explicit management-flow reason for interrupting the
  transcript
- **AND** its interaction model and visual design SHALL be rewritten to match
  the polished TUI experience

### Requirement: Integrated Textual Composer Surface
The experimental Textual TUI SHALL present the bottom composer as one cohesive
prompt control rather than a loose one-line input plus detached status widgets.

#### Scenario: Composer is idle
- **WHEN** the user is editing a prompt
- **THEN** the composer SHALL show the prompt input, action hints, attachment
  state, and suggestion state as one integrated surface
- **AND** it SHALL use theme-aware contrast and spacing instead of heavy nested
  borders
- **AND** it SHALL rely on Textual's native prompt text handling rather than a
  custom keyboard-protocol character decoding patch

#### Scenario: Composer shows suggestions
- **WHEN** slash command, file mention, or generated input suggestions are
  visible
- **THEN** the suggestion surface SHALL appear visually attached to the composer
- **AND** it SHALL NOT overlap the editable prompt text, attachment items, or
  status line incoherently

#### Scenario: Composer is busy
- **WHEN** a model turn or local command is running
- **THEN** the composer SHALL show busy or interrupt affordance without making
  the prompt area look frozen
- **AND** supported navigation and interrupt actions SHALL remain available

### Requirement: Textual Management Workflow Quality
The experimental Textual TUI SHALL provide polished management workflows for
sessions, skills, reset/config, help/status, and long detail views.

#### Scenario: Frequent decision would currently open a modal
- **WHEN** the user encounters audit approval, AskUserQuestion, or a short
  command choice during a conversation
- **THEN** the TUI SHALL prefer an inline transcript decision block over a
  blocking modal screen

#### Scenario: User opens session management
- **WHEN** the user opens session browsing or resume management
- **THEN** the TUI SHALL prefer a non-disruptive inline, side, or embedded
  surface when that preserves the conversation flow
- **AND** it SHALL show a searchable or keyboard-navigable session list
  with compact metadata and a readable preview
- **AND** it SHALL clearly mark the active or current session when applicable
- **AND** selecting, cancelling, or closing the view SHALL restore focus to the
  conversation predictably

#### Scenario: User opens skills management
- **WHEN** the user opens skills management
- **THEN** the TUI SHALL distinguish installed skills from market skills
- **AND** it SHALL expose use, view, install, uninstall, update, and refresh
  actions through visible controls or compact action rows
- **AND** long skill details SHALL remain readable without crowding the list
  layout

#### Scenario: User opens skill market
- **WHEN** the user opens the skill market or another broad skill-management
  workflow
- **THEN** the TUI MAY use a separate screen or full-surface workflow
- **AND** that workflow SHALL still be redesigned with clear navigation,
  readable density, visible actions, and predictable return to the conversation

#### Scenario: User opens reset or configuration workflow
- **WHEN** the user opens reset or configuration workflow
- **THEN** the TUI SHALL present a guided provider-aware form or staged flow
- **AND** provider, model, base URL, thinking, and theme choices SHALL show
  validation feedback near the relevant field or step
- **AND** save and cancel outcomes SHALL be explicit and shall preserve existing
  settings on cancellation

#### Scenario: User opens help status or detail views
- **WHEN** the user opens help, status, MCP, model details, skill details, or
  other long detail surfaces
- **THEN** the TUI SHALL use compact sections, grouped content, or tabs where
  appropriate
- **AND** it SHALL avoid persistent heavy footer chrome when a compact command
  strip is sufficient

#### Scenario: Management view uses a screen
- **WHEN** a management workflow uses a screen or modal surface
- **THEN** the surface SHALL use lighter chrome, compact actions,
  theme-aware styling, and predictable focus restoration

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

### Requirement: Modern UI Transcript Wheel Scrolling
Modern UI SHALL make transcript content scrollable through mouse and touchpad
wheel input while preserving prompt-focused history behavior.

#### Scenario: User scrolls transcript with mouse or touchpad
- **WHEN** the Modern UI transcript contains more content than the visible
  transcript area
- **AND** the user scrolls with a mouse wheel or touchpad over the transcript
  area
- **THEN** the transcript SHALL move through prior conversation content
- **AND** the prompt input SHALL NOT recall prompt history as a side effect of
  that scroll gesture

#### Scenario: User scrolls over transcript content
- **WHEN** the Modern UI transcript contains child blocks such as info,
  Markdown, tool, user, or assistant blocks
- **AND** the user scrolls with a mouse wheel or touchpad over one of those
  transcript child blocks
- **THEN** the parent transcript SHALL move through prior conversation content

#### Scenario: Modern UI enables terminal mouse events for transcript scrolling
- **WHEN** the Modern UI starts
- **THEN** it SHALL enable Textual mouse event handling so terminal wheel input
  can be delivered as scroll events
- **AND** it SHALL preserve the existing CJK input guard by disabling Textual's
  Kitty keyboard protocol by default while still honoring user overrides

#### Scenario: Prompt wheel gestures do not recall history
- **WHEN** the prompt input has focus and prompt history exists
- **AND** the user scrolls with a mouse wheel or touchpad over the prompt or
  composer area
- **THEN** the prompt SHALL NOT recall prompt history
- **AND** prompt history recall SHALL remain limited to keyboard navigation
  through ordinary `Up`/`Down` at prompt history boundaries and explicit
  `Ctrl+Up`/`Ctrl+Down`
- **AND** long prompt drafts MAY scroll inside the composer instead of moving
  prompt history

#### Scenario: Prompt keeps history navigation
- **WHEN** the prompt input has focus and prompt history exists
- **THEN** the prompt SHALL continue to support history recall from the composer
- **AND** `Ctrl+Up` and `Ctrl+Down` SHALL remain explicit prompt-history
  shortcuts
- **AND** Modern UI SHALL NOT require ordinary `Up` or `Down` keys to scroll
  transcript content

### Requirement: Modern UI Light Theme Choice Contrast
Modern UI SHALL provide explicit light-theme colors for prompt-adjacent
suggestions and bottom-sheet choice lists.

#### Scenario: Light theme choice surfaces are readable
- **WHEN** Modern UI is running with the shared `light` theme or a curated light
  Textual theme
- **AND** a slash suggestion list or bottom-sheet choice list is visible
- **THEN** option text, highlighted option text, disabled option text, hover
  state, and sheet background SHALL use light-theme-specific colors with clear
  contrast
- **AND** the choice list SHALL NOT rely on dark-theme foreground colors that can
  disappear against the light background

### Requirement: Modern UI Tool Transcript Ordering
Modern UI SHALL preserve visible transcript chronology for tool calls, tool
results, and local command output while updating known tool placeholders in
place.

#### Scenario: Tool result updates an existing placeholder
- **WHEN** a visible tool-call placeholder exists for a `call_id`
- **AND** the matching tool result arrives
- **THEN** Modern UI SHALL update that placeholder in place
- **AND** the tool result SHALL NOT jump to a different transcript position

#### Scenario: Later tool output has no visible placeholder
- **WHEN** a model turn has an active assistant answer block on screen
- **AND** a tool result or local command result arrives without an existing
  visible placeholder
- **THEN** Modern UI SHALL append that result at the current transcript tail
- **AND** it SHALL NOT move the result above earlier assistant, approval, or
  diff content

#### Scenario: Assistant text after visible tool output starts a new block
- **WHEN** Modern UI has rendered assistant text for the current model turn
- **AND** a later tool result, local command result, or diff block is visibly
  placed after that assistant text
- **AND** additional assistant text arrives after the tool or diff output
- **THEN** Modern UI SHALL render the additional assistant text in a new
  assistant block after the visible tool or diff output
- **AND** it SHALL NOT append the additional text back into the earlier assistant
  block above the tool output

#### Scenario: Audited tool call waits for approval context
- **WHEN** a streamed tool-call event arrives before Modern UI has shown the
  matching audit approval prompt
- **AND** the tool call has a `call_id` that is associated with the pending
  approval
- **THEN** Modern UI SHALL suppress the visible running placeholder until the
  approval context is shown and resolved
- **AND** an approved local command result SHALL NOT inherit a stale transcript
  position above the approval diff or command decision context
- **AND** the inline approval prompt SHALL visibly include the command or tool
  summary needed to decide the approval

#### Scenario: Tool call starts before assistant text
- **WHEN** a tool call placeholder is rendered before an assistant answer block
- **AND** assistant text and the matching tool result arrive later
- **THEN** Modern UI SHALL keep the tool block before the assistant answer
- **AND** the matching result SHALL update the existing tool block in place

### Requirement: Modern UI Tool Result Presentation
Modern UI SHALL render model tool results with enough foreground content for
the user to inspect them without expanding hidden details or fighting nested
scroll regions.

#### Scenario: Todo tool result shows compact todo board
- **WHEN** a `todo_write` tool result includes structured todo metadata
- **THEN** Modern UI SHALL render a visible todo block in the transcript
- **AND** the block SHALL show only a `Current` section and a `Tasks` section
  with individual todo item content
- **AND** the block SHALL use compact transcript styling that fits the current
  Modern UI block layout
- **AND** the `Current` section and task status markers SHALL be visually
  distinguishable through color or emphasis
- **AND** the block SHALL NOT show only a `Todo ok` summary line

#### Scenario: Long todo result remains compact
- **WHEN** a `todo_write` tool result contains more todo items than can be
  comfortably shown inline
- **THEN** Modern UI MAY truncate the visible todo list
- **AND** it SHALL keep current-task information visible
- **AND** it SHALL NOT introduce a nested vertical scroller for the todo list

#### Scenario: Model Shell command display omits descriptions
- **WHEN** a model-invoked Shell/CMD tool call or approval summary includes both
  a `command` and a model-provided `description`
- **THEN** Modern UI SHALL display the executable command text from `command`
- **AND** it SHALL NOT append the description as a shell comment or adjacent
  command annotation
- **AND** this requirement SHALL NOT change local `!CMD` command rendering

#### Scenario: Shell tool result keeps command visible
- **WHEN** a model-invoked Shell/CMD tool result includes command metadata
- **THEN** Modern UI SHALL render the Shell/CMD result as a single visible line
  containing the tool status and executed command
- **AND** when the Shell/CMD result metadata omits the command, Modern UI SHALL
  preserve the command from the matching `tool_call` arguments for the same
  `call_id`
- **AND** it SHALL NOT render shell status fields, exit metadata, cwd, shell
  path, dialect, or command output body in the transcript
- **AND** model-provided descriptions SHALL NOT replace or decorate the command
  text

#### Scenario: Generic tool results stay collapsed
- **WHEN** a non-Todo and non-Shell model tool result such as `WebFetch`
  completes
- **THEN** Modern UI SHALL show the tool status summary line
- **AND** it SHALL NOT render the tool output body inline in the transcript
- **AND** the result MAY still keep full output available in session context

#### Scenario: Diff transcript block has no nested vertical scroll
- **WHEN** Modern UI renders a transcript diff block for a file mutation tool
  result
- **THEN** the diff block SHALL render as normal transcript content inside the
  parent transcript scroller
- **AND** it SHALL NOT create its own vertical scroll region
- **AND** existing diff truncation MAY still limit very large diffs

### Requirement: Modern UI Foreground Background Task Listing
Modern UI SHALL distinguish user-invoked background task listing from AI/tool
background task output.

#### Scenario: User invokes ps command
- **WHEN** the user invokes `/ps` in the Modern UI prompt
- **THEN** Modern UI SHALL append the background task list to the foreground
  transcript
- **AND** each listed task SHALL include an identifier or ordinal that can be
  used by `/stop`
- **AND** the result SHALL NOT open a detached screen that hides the
  conversation transcript

#### Scenario: User-invoked slash command is recorded
- **WHEN** the user submits `/ps`, `/reset`, or another supported slash command
  from the Modern UI prompt
- **THEN** Modern UI SHALL add the submitted slash command to prompt history
- **AND** it SHALL render the submitted slash command as a user transcript entry
- **AND** the command result SHALL render in a transcript style consistent with
  other Modern UI transcript blocks when the result is shown in the transcript

#### Scenario: Tool output is not ps command output
- **WHEN** AI or tool execution creates, updates, or reports background task
  state
- **THEN** Modern UI SHALL NOT render that output as a user-invoked `/ps`
  foreground listing
- **AND** background task output SHALL remain separate from active assistant,
  thinking, and foreground command blocks

### Requirement: Modern UI Classic-Aligned Reset Workflow
Modern UI SHALL align reset/config setup with Classic UI ordering and selection
semantics instead of using a free-text all-fields form.

#### Scenario: User opens reset workflow
- **WHEN** the user invokes `/reset` in Modern UI
- **THEN** Modern UI SHALL guide the user through provider selection before API
  key entry
- **AND** it SHALL show provider-specific API key guidance after the provider is
  selected and before the API key is entered
- **AND** it SHALL then collect model, base URL, thinking mode, and UI/theme in
  the same order and with the same defaults and selection semantics as Classic
  UI setup

#### Scenario: User cancels reset workflow
- **WHEN** the user cancels the Modern UI reset workflow before saving
- **THEN** existing config SHALL remain unchanged
- **AND** partial reset values SHALL NOT be written
- **AND** the transcript or status SHALL make the cancellation outcome explicit

#### Scenario: Reset workflow saves config
- **WHEN** the user completes the Modern UI reset workflow
- **THEN** Modern UI SHALL write the selected provider, API key, model, base URL,
  thinking mode, UI, and theme to the configured config path
- **AND** Modern UI SHALL reload settings and update runtime state from the saved
  config

#### Scenario: Reset changes UI or theme selection
- **WHEN** the user completes the Modern UI reset workflow
- **AND** the selected UI or theme differs from the currently running Modern UI or
  theme selection
- **THEN** Modern UI SHALL tell the user that restarting Deepy is required for
  the UI and theme selection to take effect

### Requirement: Modern UI Subagent Report Expansion
The Modern UI SHALL make subagent reports available through a focused expansion surface while keeping non-subagent tools compact by default.

#### Scenario: Subagent report is expandable
- **WHEN** the TUI renders a completed `subagent_*` tool block with a returned report
- **THEN** the collapsed block SHALL remain a compact subagent status summary
- **AND** the collapsed block SHALL show a bounded `Subagent Parameters` section when assigned parameters are available
- **AND** expanding the block SHALL reveal a bounded final subagent report
- **AND** the expanded report SHALL be styled as subagent-specific detail content distinct from ordinary tool metadata

#### Scenario: Non-subagent tool output stays hidden
- **WHEN** the TUI renders a regular non-subagent tool block without a dedicated visible surface
- **AND** the user toggles expansion on that block
- **THEN** the TUI SHALL keep that tool's raw output body hidden
- **AND** it SHALL NOT expose generic tool output only because subagent report expansion exists

#### Scenario: Subagent visual state is scannable
- **WHEN** a subagent block is running, completed, failed, or expanded
- **THEN** the TUI SHALL use state-aware colors consistent with existing Modern UI tool states
- **AND** it SHALL keep subagent parameters and progress text visually quieter than the final report

### Requirement: Textual Status Session Metadata Resilience
The experimental Textual TUI SHALL treat session metadata used by the status bar
and side panel as best-effort display data. Failures while reading session
metadata MUST NOT crash the Textual app, interrupt stream rendering, or prevent
the active turn from completing.

#### Scenario: Status metadata read fails during idle rendering
- **WHEN** the experimental TUI renders its status bar or side panel
- **AND** reading the active session metadata fails
- **THEN** the TUI SHALL continue rendering the status bar and side panel
- **AND** it SHALL show unknown or unavailable context/cache metadata
- **AND** it SHALL NOT raise the session metadata read failure through the
  Textual message loop

#### Scenario: Status metadata read fails during streaming
- **WHEN** a model turn is streaming text, reasoning, raw response, tool call, or
  tool output events
- **AND** reading the active session metadata fails
- **THEN** the TUI SHALL continue processing stream events
- **AND** it SHALL preserve live progress status such as running state, token
  progress, or tool status
- **AND** it SHALL show unknown or unavailable context/cache metadata until a
  later successful metadata refresh

### Requirement: Textual Status Session Metadata Refresh Frequency
The experimental Textual TUI SHALL avoid high-frequency repeated session-list
reads when updating live status. Session metadata for status bar and side-panel
context/cache display MUST be cached or otherwise reused across stream status
updates, and refreshed only at meaningful lifecycle points.

#### Scenario: Streaming status updates reuse cached metadata
- **WHEN** a model turn emits multiple stream events that update live status
- **THEN** the TUI SHALL NOT call the session-list reader once per stream event
- **AND** it SHALL render status bar and side-panel context/cache information
  from cached metadata or from an unavailable fallback

#### Scenario: Metadata refreshes after session lifecycle changes
- **WHEN** the active session changes, a model turn completes, a session is
  resumed, a new session starts, or an explicit session lifecycle command
  refreshes session state
- **THEN** the TUI SHALL refresh the cached session metadata used by status bar
  and side-panel context/cache display
- **AND** subsequent status renders SHALL use the refreshed metadata until the
  next lifecycle refresh or fallback state

#### Scenario: Explicit session commands remain fresh
- **WHEN** a user invokes a Textual TUI command whose purpose is to list, resume,
  inspect, or summarize sessions
- **THEN** the command MAY read the session list directly
- **AND** the direct read SHALL NOT be part of per-token or per-stream-event
  status rendering

### Requirement: Modern UI source package

The experimental Textual TUI implementation SHALL live under `deepy.ui.modern` and
MUST NOT depend on a separate top-level `deepy.tui` package.

#### Scenario: Maintainer imports the TUI app

- **WHEN** code loads the Textual application entry point
- **THEN** it SHALL import from `deepy.ui.modern` (for example `deepy.ui.modern.app`
  or `deepy.ui.modern.runner`)
- **AND** the repository SHALL NOT ship `deepy.tui` as an installable package path

#### Scenario: User starts the experimental TUI

- **WHEN** a user runs `deepy tui`
- **THEN** Deepy SHALL start the Textual UI through `deepy.ui.modern` without
  importing `deepy.tui`

