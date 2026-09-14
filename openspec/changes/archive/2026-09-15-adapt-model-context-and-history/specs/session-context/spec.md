## MODIFIED Requirements

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

- **WHEN** Deepy reports Context Window usage after a model request with known usage and a checkpoint matching the current provider/model/API and active history view
- **THEN** the reported used value SHALL come from the latest request context occupancy
- **AND** the reported total value SHALL come from the resolved effective model context window
- **AND** the reported remaining value SHALL be the resolved effective model context window minus latest request context occupancy

### Requirement: Context And Compact Display

Deepy SHALL show Context Window occupancy as the only user-facing context pressure value, and automatic compaction timing SHALL use the complete next-request budget with only identity-compatible usage checkpoints used for calibration.

#### Scenario: A model turn completes

- **WHEN** Deepy receives usage for one or more model requests in a user turn
- **THEN** it SHALL display per-turn Token Usage details after the response
- **AND** it SHALL update the Context Window display with latest request used tokens, total context window, remaining tokens, and percentage
- **AND** it SHALL NOT show a separate `compact` or compaction pressure token segment
- **AND** it SHALL combine compatible latest request usage with uncovered input and current request overhead when determining whether the next turn should auto compact

#### Scenario: A session is compacted

- **WHEN** manual or automatic compaction rewrites a session
- **THEN** Deepy SHALL update the persisted session history to the compacted summary plus preserved recent context
- **AND** this explicit rewrite SHALL reset the persisted Context Window checkpoint to the compacted session estimate
- **AND** the next Context Window display and auto-compact decision SHALL use the reset checkpoint until a newer provider usage record is available
- **AND** any user-facing compaction summary SHALL identify whether its before value is reported occupancy or a next-request estimate, consistently with the statusline

#### Scenario: Interrupted prompt rollback preserves latest context checkpoint

- **WHEN** an Esc interrupt rolls back only the newly persisted user prompt
- **AND** the active session already has a latest request Context Window checkpoint
- **THEN** Deepy SHALL preserve that latest request Context Window checkpoint
- **AND** it SHALL NOT replace the checkpoint with internal active-token estimates
- **AND** it MAY update active-token and pending-token metadata used for compaction decisions

#### Scenario: Pending context exists

- **WHEN** session messages have been appended after the latest precise usage checkpoint
- **THEN** Deepy SHALL NOT show pending estimated tokens as a separate statusline pressure value
- **AND** it SHALL keep the latest reported value distinct from any labeled next-request estimate
- **AND** automatic compaction SHALL include pending tokens even when a reported checkpoint exists

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
- **THEN** Deepy SHALL block an incompatible model request with guidance to select an image-capable model, start a text-only session or explicitly request a text summary for the selected model
- **AND** it SHALL preserve the original image attachments and text context
- **AND** it SHALL NOT silently strip image history or mutate the original session

#### Scenario: Compacted image context
- **WHEN** retained model context contains only a text summary after compaction
- **THEN** Deepy SHALL permit that text context for a text-only model
- **AND** it SHALL preserve original attachments in persisted session history

## ADDED Requirements

### Requirement: Context Checkpoint Identity
Deepy SHALL associate context checkpoints with the request model, endpoint, active history revision and prompt/tool definitions.

#### Scenario: Checkpoint no longer matches
- **WHEN** model, endpoint, history view or prompt/tool definitions change
- **THEN** Deepy SHALL stop presenting the old checkpoint as precise target-model occupancy
- **AND** it SHALL estimate the complete target replay until matching usage is received, without altering cumulative historical usage

#### Scenario: Prepared view commits
- **WHEN** a target view is fully prepared and its source history revision still matches
- **THEN** Deepy SHALL atomically persist its summary references, coverage and model provenance while retaining original records
- **AND** resume SHALL recover the committed view or the previous valid view after interruption, never a partial replacement
