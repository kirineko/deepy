## ADDED Requirements

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
