# Session And Context Specification

## Purpose

Deepy stores project conversations as local JSONL sessions, keeps usage visible,
and estimates context pressure for compaction.
## Requirements
### Requirement: Session Commands
Deepy SHALL keep the user-facing session commands available.

#### Scenario: User manages sessions
- **WHEN** a user runs `/resume`, `deepy sessions list`, or `deepy sessions show`
- **THEN** Deepy SHALL list, select, and display session history from the
  transactional local session store

### Requirement: Usage Accounting

Deepy SHALL normalize token usage from DeepSeek and the OpenAI Agents SDK while keeping API usage accounting and latest request context occupancy separate.

#### Scenario: DeepSeek usage is received

- **WHEN** usage includes `prompt_tokens`, `completion_tokens`, `total_tokens`, cache hit/miss tokens, or reasoning tokens
- **THEN** Deepy SHALL normalize those fields into `TokenUsage`
- **AND** it SHALL preserve them for per-turn and accumulated usage reporting
- **AND** it SHALL derive latest request context occupancy from input context tokens plus output tokens without double counting cache detail fields already included in prompt tokens
- **AND** it SHALL NOT treat cumulative `total_tokens` as the Context Window used value

#### Scenario: Agents SDK usage is received

- **WHEN** usage includes `input_tokens`, `output_tokens`, `input_tokens_details`, or `output_tokens_details`
- **THEN** Deepy SHALL normalize those fields into `TokenUsage`
- **AND** it SHALL preserve them for per-turn and accumulated usage reporting
- **AND** it SHALL derive latest request context occupancy from normalized input, output, and cache fields using provider semantics that avoid double counting
- **AND** it SHALL keep accumulated Token Usage separate from latest request Context Window usage

#### Scenario: Cumulative usage is reported

- **WHEN** Deepy reports Token Usage for a turn or session
- **THEN** the reported value SHALL represent cumulative API consumption for the selected scope
- **AND** it SHALL NOT be used as the Context Window used value
- **AND** it SHALL preserve request count, cache, reasoning, input, output, and total fields when known

#### Scenario: Latest request context usage is reported

- **WHEN** Deepy reports Context Window usage after at least one model request with known usage
- **THEN** the reported used value SHALL come from the latest request context occupancy
- **AND** the reported total value SHALL come from the configured context window
- **AND** the reported remaining value SHALL be the configured context window minus latest request context occupancy

### Requirement: Context And Compact Display

Deepy SHALL show Context Window occupancy as the only user-facing context pressure value, and automatic compaction timing SHALL use latest request Context Window usage when available.

#### Scenario: A model turn completes

- **WHEN** Deepy receives usage for one or more model requests in a user turn
- **THEN** it SHALL display per-turn Token Usage details after the response
- **AND** it SHALL update the Context Window display with latest request used tokens, total context window, remaining tokens, and percentage
- **AND** it SHALL NOT show a separate `compact` or compaction pressure token segment
- **AND** it SHALL use latest request Context Window usage to determine whether the next turn should auto compact when that usage is available

#### Scenario: A session is compacted

- **WHEN** manual or automatic compaction rewrites a session
- **THEN** Deepy SHALL update the persisted session history to the compacted summary plus preserved recent context
- **AND** this explicit rewrite SHALL reset the persisted Context Window checkpoint to the compacted session estimate
- **AND** the next Context Window display and auto-compact decision SHALL use the reset checkpoint until a newer provider usage record is available
- **AND** any user-facing compaction summary SHALL report its before value from the same Context Window checkpoint shown in the statusline when that checkpoint is available

#### Scenario: Interrupted prompt rollback preserves latest context checkpoint

- **WHEN** an Esc interrupt rolls back only the newly persisted user prompt
- **AND** the active session already has a latest request Context Window checkpoint
- **THEN** Deepy SHALL preserve that latest request Context Window checkpoint
- **AND** it SHALL NOT replace the checkpoint with internal active-token estimates
- **AND** it MAY update active-token and pending-token metadata used for compaction decisions

#### Scenario: Pending context exists

- **WHEN** session messages have been appended after the latest precise usage checkpoint
- **THEN** Deepy SHALL NOT show pending estimated tokens as a separate statusline pressure value
- **AND** it SHALL NOT add pending estimated tokens to the latest request Context Window used value

#### Scenario: Provider usage is unknown

- **WHEN** the latest model request does not provide usable token usage
- **THEN** Deepy SHALL render Context Window usage as unknown or estimated
- **AND** it SHALL NOT substitute cumulative Token Usage as Context Window usage
- **AND** automatic compaction MAY fall back to local history estimates to avoid sending obviously oversized requests

#### Scenario: Latest request reaches compaction threshold

- **WHEN** latest request Context Window used tokens are greater than or equal to the configured context window multiplied by the compact trigger ratio
- **THEN** Deepy SHALL automatically compact before the next model request
- **AND** the same condition SHALL drive any `compact next` statusline hint

#### Scenario: A new session is started

- **WHEN** the user starts a new session
- **THEN** Deepy SHALL clear the active session Context Window checkpoint from the statusline
- **AND** it SHALL NOT carry the previous session's Context Window used value or `compact next` hint into the new session

### Requirement: Manual Session Compaction

Deepy SHALL provide a durable session compaction operation that replaces older
active session history with a model-generated summary while preserving recent
context.

#### Scenario: Active session is compacted manually

- **WHEN** a user requests compaction for an active session
- **THEN** Deepy SHALL generate a structured summary from older session items
- **AND** it SHALL preserve configured recent session items after the summary
- **AND** it SHALL rewrite the active session so `/resume` continues from the
  compacted context

#### Scenario: Manual compaction includes a focus instruction

- **WHEN** a user requests compaction with an additional focus instruction
- **THEN** Deepy SHALL include that instruction in the compaction prompt
- **AND** the generated summary SHALL prioritize the requested focus without
  dropping current task state

#### Scenario: Session has too little history to compact

- **WHEN** manual compaction is requested for a session with no eligible older
  history
- **THEN** Deepy SHALL leave the active session unchanged
- **AND** it SHALL report that there is no context to compact

### Requirement: Legacy Context Logic Retirement

Deepy SHALL remove the old placeholder compaction and silent model-input
trimming behavior from the active context management path.

#### Scenario: Old placeholder compaction entry point is called

- **WHEN** an internal caller requests session compaction through the existing
  session manager API
- **THEN** Deepy SHALL delegate to the durable compaction service
- **AND** it SHALL NOT clear history and replace it with a static placeholder
  message

#### Scenario: Model input is prepared for a turn

- **WHEN** Deepy prepares session history for an Agents SDK model run
- **THEN** the preparation step SHALL NOT silently drop older persisted items as
  a substitute for compaction
- **AND** any required compaction SHALL have already completed through the
  durable pre-run compaction flow

#### Scenario: Context is too large after required compaction fails

- **WHEN** Deepy cannot compact a session that exceeds policy
- **THEN** it SHALL stop before the model request
- **AND** it SHALL report a clear context compaction error instead of sending a
  silently trimmed request

### Requirement: Compaction Recoverability
Deepy SHALL preserve the pre-compaction session history before replacing the
active session.

#### Scenario: Compaction succeeds
- **WHEN** Deepy successfully generates a compaction summary and replacement
  history
- **THEN** it SHALL archive or snapshot the original active session history
  before making the replacement history active
- **AND** it SHALL make the active replacement and updated session metadata
  visible atomically

#### Scenario: Summary generation fails
- **WHEN** the compaction model call fails
- **THEN** Deepy SHALL leave the original active session history unchanged
- **AND** it SHALL report the compaction failure to the caller

#### Scenario: Replacement write fails
- **WHEN** Deepy cannot persist the replacement history or its metadata
- **THEN** it SHALL roll back to the original active session history when
  possible
- **AND** it SHALL NOT leave the active session in a partially compacted state

### Requirement: Automatic Session Compaction

Deepy SHALL automatically compact the active session before a model turn when effective session context pressure exceeds configured policy.

#### Scenario: Ratio trigger is reached

- **WHEN** the effective active context tokens are greater than or equal to the configured compact trigger ratio of the context window
- **THEN** Deepy SHALL run durable session compaction before sending the next model request
- **AND** the model request SHALL use the compacted session history
- **AND** the decision SHALL NOT be bypassed by a smaller latest-turn API usage record

#### Scenario: Reserved context trigger is reached

- **WHEN** the effective active context tokens plus the configured reserved context tokens are greater than or equal to the context window
- **THEN** Deepy SHALL run durable session compaction before sending the next model request
- **AND** the model request SHALL use the compacted session history
- **AND** the decision SHALL NOT be bypassed by a smaller latest-turn API usage record

#### Scenario: Automatic compaction fails

- **WHEN** automatic compaction is required but fails
- **THEN** Deepy SHALL leave the active session unchanged
- **AND** it SHALL stop the model turn with a clear compaction error instead of silently sending an oversized request

### Requirement: Pending Context Token Accounting

Deepy SHALL account for messages appended after the latest precise context checkpoint when deciding context pressure.

#### Scenario: Usage update is recorded

- **WHEN** a model turn returns precise context usage
- **THEN** Deepy SHALL store that usage as a context checkpoint for the session only under rules that preserve effective context correctness
- **AND** it SHALL reset pending token estimate for messages covered by that usage
- **AND** it SHALL NOT reduce effective context tokens for ordinary appended history unless a history rewrite has occurred

#### Scenario: Messages are appended after usage

- **WHEN** user, assistant, or tool messages are appended after the latest precise usage checkpoint
- **THEN** Deepy SHALL add estimated tokens for those messages to the session pending token estimate
- **AND** automatic compaction SHALL use precise checkpoint tokens plus pending estimated tokens

#### Scenario: Session is restored

- **WHEN** Deepy restores a session with token checkpoint metadata
- **THEN** it SHALL reconstruct the effective active token estimate from the latest checkpoint and messages appended after that checkpoint
- **AND** if checkpoint metadata appears missing or undercounted, Deepy SHALL fall back to a safe estimate from replayable session records

### Requirement: Local Command Transcript Persistence
Deepy SHALL persist local command-mode input and output in the active session so
later model turns can use the command result as context.

#### Scenario: Local command completes
- **WHEN** a local command-mode command completes
- **THEN** Deepy SHALL append the literal `!` command input to the active session
  as a user item
- **AND** it SHALL append a synthetic assistant shell tool call item for the
  command
- **AND** it SHALL append a matching synthetic shell tool result item containing
  the command result

#### Scenario: Later model turn replays session
- **WHEN** Deepy prepares session history for a later model turn
- **THEN** the previously recorded local command transcript SHALL be included in
  the replayed session input
- **AND** the model SHALL be able to see both the local command and its stored
  output

#### Scenario: Local command output is stored
- **WHEN** Deepy stores a local command result in the session
- **THEN** it SHALL apply a context-storage output limit independent of the
  terminal display limit
- **AND** stored metadata SHALL indicate when output was truncated for context

#### Scenario: Windows local command output is stored
- **WHEN** Deepy stores a Windows local command result in the session
- **THEN** the stored shell output SHALL decode Windows-native command output
  into readable Unicode text before persistence
- **AND** it SHALL use normalized line endings
- **AND** it SHALL NOT include terminal control sequences that were removed from
  user-facing display
- **AND** it SHALL preserve printable Unicode command output

#### Scenario: Local command result metadata is stored
- **WHEN** Deepy stores a local command result
- **THEN** the synthetic shell result SHALL include command-mode metadata such as
  cwd, shell kind, command dialect, TTY mode, exit code, duration, and
  interruption or timeout state when available

#### Scenario: Local command does not call the model
- **WHEN** a local command-mode command is handled
- **THEN** Deepy SHALL NOT record model token usage for that command
- **AND** it SHALL update local context estimates from the appended session
  records so the status footer reflects pending context

#### Scenario: Local command history is shown
- **WHEN** a session containing local command-mode records is displayed or
  resumed
- **THEN** Deepy SHALL render the synthetic shell result using the existing
  shell output display path

### Requirement: Todo State Persistence

Deepy SHALL preserve the latest valid todo plan with the active session.

#### Scenario: Todo plan is updated

- **WHEN** `todo_write` successfully updates the active todo plan
- **THEN** Deepy SHALL persist the latest todo state with the active session
- **AND** the persisted state SHALL be sufficient to restore the board without
  reparsing assistant prose

#### Scenario: Session is resumed

- **WHEN** a user resumes a session with a persisted todo plan
- **THEN** Deepy SHALL restore the latest valid todo state
- **AND** the terminal UI SHALL be able to render the restored todo board or
  compact summary

#### Scenario: Session is compacted

- **WHEN** manual or automatic compaction rewrites a session that has an active
  todo plan
- **THEN** Deepy SHALL preserve the latest todo state across the compaction
- **AND** the compaction prompt SHALL include enough todo context for the model
  to continue or reconcile the plan

#### Scenario: Invalid todo update occurs

- **WHEN** a `todo_write` call fails validation
- **THEN** Deepy SHALL NOT persist the invalid todo list
- **AND** it SHALL keep the latest previous valid todo state for resume and
  compaction

### Requirement: Textual Session Commands
The experimental Textual TUI SHALL expose session lifecycle commands through
Textual-native surfaces.

#### Scenario: User starts a new TUI session
- **WHEN** a user invokes `/new` in the experimental TUI
- **THEN** the TUI SHALL clear the active session id
- **AND** it SHALL reset loaded per-session TUI state that should not carry into
  the new conversation
- **AND** it SHALL keep global settings unchanged

#### Scenario: User lists TUI sessions
- **WHEN** a user invokes `/sessions` in the experimental TUI
- **THEN** the TUI SHALL show project session entries in a navigable Textual
  surface
- **AND** each entry SHALL include session id, title or first prompt, status,
  timestamp, and available history estimate when known

#### Scenario: User resumes a TUI session
- **WHEN** a user selects a session from `/resume` or the sessions surface
- **THEN** the TUI SHALL set that session as active
- **AND** it SHALL restore visible transcript history from the session when
  available
- **AND** subsequent prompts SHALL continue that session id

#### Scenario: User cancels session selection
- **WHEN** a user cancels the session picker
- **THEN** the TUI SHALL keep the previous active session unchanged
- **AND** focus SHALL return to the prompt or prior conversation surface

### Requirement: Textual Manual Compaction
The experimental Textual TUI SHALL expose manual session compaction for the
active session.

#### Scenario: User compacts active TUI session
- **WHEN** a user invokes `/compact` in the experimental TUI with an active
  session
- **THEN** Deepy SHALL run the existing durable session compaction flow
- **AND** the TUI SHALL show running, success, no-op, or failure state in the
  transcript or status surface
- **AND** the active session id SHALL remain usable after compaction

#### Scenario: User provides compaction focus
- **WHEN** a user invokes `/compact` with a focus instruction
- **THEN** the TUI SHALL pass the focus instruction to the compaction flow
- **AND** the compaction summary SHALL prioritize that focus according to the
  existing session-context contract

#### Scenario: User compacts without active session
- **WHEN** a user invokes `/compact` before a TUI session exists
- **THEN** the TUI SHALL report that there is no active session to compact
- **AND** it SHALL NOT start a model turn

### Requirement: Textual Local Command Session Persistence
The experimental Textual TUI SHALL persist local command-mode input and output
using the same synthetic shell transcript records as the stable terminal UI.

#### Scenario: TUI local command completes
- **WHEN** a TUI local command-mode command completes
- **THEN** Deepy SHALL append the literal `!` command input to the active
  session as a user item
- **AND** it SHALL append a synthetic assistant shell tool call item
- **AND** it SHALL append a matching synthetic shell tool result item
  containing the command result
- **AND** the TUI SHALL update its active session id when persistence creates a
  new session

#### Scenario: TUI local command output is stored
- **WHEN** the TUI stores a local command result in the session
- **THEN** it SHALL apply the same context-storage output limit used by stable
  local command mode
- **AND** stored metadata SHALL indicate when output was truncated for context

#### Scenario: TUI Windows local command output is stored
- **WHEN** the TUI stores a Windows local command result in the session
- **THEN** the stored shell output SHALL decode Windows-native command output
  into readable Unicode text before persistence
- **AND** it SHALL use normalized line endings
- **AND** it SHALL NOT include terminal control sequences that were removed from
  user-facing display

#### Scenario: TUI resumes local command history
- **WHEN** the TUI restores a session containing local command-mode records
- **THEN** it SHALL render the synthetic shell result through the same shell
  output display path used for model-invoked shell tool results

### Requirement: Input Suggestion Usage Separation
Deepy SHALL keep input suggestion token usage separate from ordinary session
turn usage and context window accounting.

#### Scenario: Suggestion usage is recorded
- **WHEN** an input suggestion model call returns known token usage
- **THEN** Deepy SHALL record the usage under an input-suggestion-specific
  accounting field or record type
- **AND** it SHALL preserve request count, input tokens, output tokens, cache
  tokens, reasoning tokens when present, total tokens, model, and elapsed time
  when known

#### Scenario: Ordinary turn usage is reported
- **WHEN** Deepy displays or persists usage for a submitted user turn
- **THEN** input suggestion usage SHALL NOT be merged into that turn's
  `TokenUsage`
- **AND** the ordinary turn usage footer SHALL remain scoped to the submitted
  turn

#### Scenario: Context window checkpoint is updated
- **WHEN** input suggestion usage is recorded
- **THEN** Deepy SHALL NOT update the latest request Context Window usage
  checkpoint from the suggestion request
- **AND** automatic compaction decisions SHALL NOT treat suggestion usage as
  active conversation context usage

#### Scenario: Accumulated usage is summarized
- **WHEN** Deepy shows accumulated session or exit usage and input suggestion
  usage is known
- **THEN** Deepy SHALL show input suggestion usage separately from cumulative
  model-turn usage
- **AND** it SHALL label the input suggestion usage so users can distinguish
  background suggestion cost from submitted prompt cost

### Requirement: Status Usage Scopes
Deepy SHALL report Token Usage in `/status` using explicit local scopes while preserving the existing separation between cumulative API usage and latest request Context Window occupancy.

#### Scenario: Active session usage is known
- **WHEN** the user runs `/status`
- **AND** an active session exists with persisted Token Usage
- **THEN** Deepy SHALL show active-session Token Usage as cumulative API consumption for that session
- **AND** it SHALL include known request count, input, output, cache, reasoning, and total token fields in compact form

#### Scenario: Project usage is known
- **WHEN** the user runs `/status`
- **AND** the project session index contains persisted Token Usage for one or more sessions
- **THEN** Deepy SHALL show project-level Token Usage by merging known session usage records
- **AND** it SHALL treat sessions without usage metadata as unknown rather than inventing usage

#### Scenario: Context window status is shown
- **WHEN** the user runs `/status`
- **AND** latest request Context Window usage is known for the active session
- **THEN** Deepy SHALL show Context Window used tokens, total context window tokens, remaining tokens, and percentage
- **AND** it SHALL NOT substitute cumulative Token Usage totals as Context Window used tokens

#### Scenario: Usage is unavailable
- **WHEN** the user runs `/status`
- **AND** active-session or project Token Usage is not known
- **THEN** Deepy SHALL render that usage scope as unknown or unavailable
- **AND** it SHALL keep the rest of the status panel visible

### Requirement: Session Cost Snapshot Metadata
Deepy SHALL persist optional session cost metadata separately from Token Usage
and Context Window accounting.

#### Scenario: Session balance snapshots are recorded
- **WHEN** Deepy records starting and ending DeepSeek balance snapshots for an
  interactive session
- **THEN** it SHALL store the snapshot metadata with the session index entry
- **AND** it SHALL preserve each known currency independently
- **AND** it SHALL store enough information to render starting balance, ending
  balance, computed spend, and unavailable reason when known

#### Scenario: Cost metadata is absent
- **WHEN** Deepy reads an existing session index entry without cost metadata
- **THEN** it SHALL treat session cost as unknown
- **AND** it SHALL keep existing session usage, input suggestion usage, active
  token estimates, and Context Window checkpoints intact

#### Scenario: Session cost is computed
- **WHEN** a session has valid starting and ending balances for the same
  currency
- **THEN** Deepy SHALL compute spend from the positive decrease in
  `total_balance`
- **AND** it SHALL NOT use cumulative Token Usage totals as money values
- **AND** it SHALL NOT update Context Window usage or compaction checkpoints
  from cost metadata

#### Scenario: Balance delta is not reliable
- **WHEN** either balance snapshot is unavailable, currencies do not match, or
  a balance increases during the session
- **THEN** Deepy SHALL mark session cost as unavailable or not measurable for
  that currency
- **AND** it SHALL keep local usage metadata visible to callers

### Requirement: Subagent Session Recording

Deepy SHALL record subagent activity enough for session replay and cost/context
awareness without treating full subagent transcripts as ordinary main-thread
conversation history.

#### Scenario: Subagent lifecycle event is emitted

- **WHEN** a subagent starts, completes, fails, or requires approval
- **THEN** Deepy SHALL record a replay-safe event or item representing that
  lifecycle state
- **AND** replay SHALL render the lifecycle event without requiring the subagent
  to run again

#### Scenario: Subagent returns a result

- **WHEN** a subagent returns a final report to the main agent
- **THEN** Deepy SHALL preserve the report needed for the main agent's
  continuation and session replay
- **AND** it SHALL avoid duplicating the entire nested subagent transcript into
  the main session context unless explicitly required for correctness

#### Scenario: Subagent usage is known

- **WHEN** subagent token usage is available from the SDK run result
- **THEN** Deepy SHOULD account for that usage in session usage reporting
- **AND** it SHOULD distinguish subagent usage from main-agent usage when the
  data is available

### Requirement: Transactional Local Session Store
Deepy SHALL store active project sessions in a transactional local session store
that keeps session metadata and ordered replay items together.

#### Scenario: A session item is appended
- **WHEN** Deepy writes a new session item
- **THEN** it SHALL store the replayable OpenAI Agents SDK item as the canonical
  item payload
- **AND** it SHALL update the session metadata required for listing, resume,
  context accounting, and status in the same transaction

#### Scenario: A session is replayed
- **WHEN** Deepy replays a session
- **THEN** it SHALL read model replay items from the canonical stored SDK item
  payloads ordered by their session sequence
- **AND** it SHALL NOT rely on display-only history records or historical JSONL
  wrapper fields

#### Scenario: Latest session items are restored
- **WHEN** Deepy restores only the latest visible history for resume or TUI
  rendering
- **THEN** it SHALL read only the requested tail of ordered session items when a
  limit is provided
- **AND** it SHALL preserve the same replay sanitization behavior used for full
  session replay

#### Scenario: Historical JSONL files exist
- **WHEN** a project directory contains old JSONL session files or
  `sessions-index.json`
- **THEN** Deepy SHALL NOT load those files into the active session list
- **AND** it SHALL NOT use them as fallback metadata for replay, resume, context
  accounting, todo state, usage, cost, or process cleanup

### Requirement: Storage-Neutral Session API
Deepy SHALL expose session operations through storage-neutral session APIs rather
than JSONL-specific names or contracts.

#### Scenario: Internal caller opens a session
- **WHEN** runner, compaction, UI, TUI, status, local command, or input
  suggestion code opens a Deepy session
- **THEN** it SHALL use a storage-neutral session abstraction
- **AND** the abstraction SHALL satisfy the OpenAI Agents SDK session protocol
  used by model runs

#### Scenario: Session entries are listed
- **WHEN** Deepy lists project sessions
- **THEN** it SHALL return session entries from the transactional store
- **AND** each entry SHALL include the metadata required by existing session
  pickers, status reports, process cleanup, usage display, and cost summaries

### Requirement: Cache-First Session Context
Deepy SHALL model model-visible session context as a stable prefix plus an
append-only session log plus volatile scratch state.

#### Scenario: Normal turn appends context
- **WHEN** a user prompt, assistant response, reasoning content, tool call, or
  tool result is recorded during a normal model turn
- **THEN** Deepy SHALL append the resulting session item after existing active
  items
- **AND** it SHALL NOT rewrite earlier active items as part of the normal turn

#### Scenario: Volatile state changes
- **WHEN** Deepy updates transient runtime state such as live progress, UI-only
  status, temporary planning notes, or diagnostics
- **THEN** it SHALL keep that state outside the replayed model-visible session
  log unless a later step explicitly distills it into persisted session content

#### Scenario: Session resumes
- **WHEN** Deepy resumes a saved session
- **THEN** it SHALL restore the append-only log and cache metadata
- **AND** it SHALL compare the saved cache-prefix fingerprint with the current
  prefix snapshot before the next model request

### Requirement: Explicit Cache Break Recording
Deepy SHALL record cache-breaking context events instead of silently changing
the effective model-visible prefix or log.

#### Scenario: Active history is rewritten
- **WHEN** Deepy compacts, archives and replaces, retries by rolling back,
  recovers from an interrupt by removing active items, or otherwise rewrites
  existing active session items
- **THEN** it SHALL increment the cache context generation
- **AND** it SHALL persist a concise cache break reason with the session

#### Scenario: Prefix source changes
- **WHEN** the active model id, reasoning settings, system prompt stable blocks,
  loaded skill/rule blocks, runtime context boundary, built-in tool schema, or
  MCP tool schema set changes
- **THEN** Deepy SHALL increment the prefix generation before the next model
  request
- **AND** it SHALL persist a cache break reason naming the changed source

#### Scenario: New session starts
- **WHEN** Deepy starts a new session
- **THEN** it SHALL initialize cache metadata for a new prefix generation
- **AND** it SHALL NOT carry cache hit aggregates or cache break reasons from
  the previous session

### Requirement: Cache Usage Aggregation
Deepy SHALL persist cache usage statistics for each session from normalized
provider usage events.

#### Scenario: Usage event includes cache tokens
- **WHEN** a model turn reports `prompt_cache_hit_tokens` and
  `prompt_cache_miss_tokens`
- **THEN** Deepy SHALL persist the per-turn cache hit and miss tokens
- **AND** it SHALL update session-level cache hit and miss aggregates
- **AND** it SHALL compute a session cache hit ratio when the denominator is
  non-zero

#### Scenario: Usage event has no cache token data
- **WHEN** a provider usage event does not include cache hit or miss tokens
- **THEN** Deepy SHALL preserve the model turn usage
- **AND** it SHALL mark cache usage for that turn as unknown rather than zero

### Requirement: Cache-Aligned Context Folding
Deepy SHALL fold or compact context in a way that preserves cache reuse where
possible and records the active-history rewrite where unavoidable.

#### Scenario: Fold request is built
- **WHEN** Deepy builds a summary or fold request for a long session
- **THEN** it SHALL reuse the current stable prefix snapshot where the provider
  boundary permits it
- **AND** it SHALL preserve source conversation content order in the summary
  request
- **AND** it SHALL place the summarization instruction after the source content

#### Scenario: Fold result replaces active history
- **WHEN** Deepy replaces active history with a compacted summary and tail
- **THEN** it SHALL persist the replacement
- **AND** it SHALL record that compaction caused a cache break
- **AND** subsequent status surfaces SHALL be able to show the break reason

### Requirement: Breaking File Tool History Boundary
Deepy SHALL treat the v3 file tool rewrite as a breaking history boundary paired
with the session/history storage rewrite.

#### Scenario: Old file-tool transcript is encountered
- **WHEN** Deepy encounters old persisted session content that contains
  `read_file`, `edit_text`, `write_file`, or `apply_patch` tool calls or results
  after the v3 file tool release
- **THEN** Deepy SHALL NOT be required to replay, resume, execute, or render
  those old file-tool records through compatibility shims
- **AND** it MAY report that the old session content is unsupported by the
  current breaking release

#### Scenario: New session records v3 file tools
- **WHEN** a new model turn records file tool activity after the v3 file tool
  release
- **THEN** session history SHALL persist the model-visible `Read`, `Write`, and
  `Update` calls and results as the canonical file-tool records
- **AND** it SHALL NOT synthesize old v2 file-tool records for compatibility

### Requirement: Image Attachment Session Persistence
Deepy SHALL persist user turns with image attachments so supported image conversations remain resumable.

#### Scenario: Image prompt is recorded
- **WHEN** a user submits a prompt with one or more image attachments
- **THEN** Deepy SHALL record the user turn with structured text and image content
- **AND** the persisted item SHALL contain enough information to replay the image context in a resumed session

#### Scenario: Image session is resumed
- **WHEN** the user resumes a session containing image prompt turns
- **THEN** Deepy SHALL load the image content as structured session input
- **AND** subsequent model turns SHALL preserve the conversation context when the active model supports image input

#### Scenario: Image session is resumed with unsupported model
- **WHEN** the user resumes a session containing image prompt turns
- **AND** the active model does not support image input
- **THEN** Deepy SHALL ignore image content blocks for that model turn
- **AND** it SHALL preserve and send the remaining text context
- **AND** it SHALL NOT block the model request with an incompatibility message

### Requirement: Image Attachment Preview Redaction
Deepy SHALL keep image session previews readable by redacting raw image data in normal user-facing displays.

#### Scenario: Session list previews image prompt
- **WHEN** Deepy renders a session list entry whose title or preview comes from an image prompt
- **THEN** it SHALL show prompt text and compact image labels
- **AND** it SHALL NOT show raw base64 data or full data URLs

#### Scenario: Session show renders image prompt
- **WHEN** Deepy renders session history containing image content blocks
- **THEN** it SHALL show compact image labels or image metadata
- **AND** it SHALL NOT show raw base64 data in normal non-debug output

#### Scenario: Context tokens are estimated for image prompts
- **WHEN** Deepy estimates local context pressure for persisted image prompt items
- **THEN** it SHALL account for image content conservatively
- **AND** it SHALL avoid expanding redacted display labels back into raw base64 for user-facing context summaries

