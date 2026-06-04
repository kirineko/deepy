## ADDED Requirements

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

## MODIFIED Requirements

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
