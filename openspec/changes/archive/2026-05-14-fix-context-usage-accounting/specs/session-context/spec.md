## MODIFIED Requirements

### Requirement: Usage Accounting

Deepy SHALL normalize token usage from DeepSeek and the OpenAI Agents SDK while keeping API usage accounting separate from session context occupancy.

#### Scenario: DeepSeek usage is received

- **WHEN** usage includes `prompt_tokens`, `completion_tokens`, `total_tokens`, cache hit/miss tokens, or reasoning tokens
- **THEN** Deepy SHALL normalize those fields into `TokenUsage`
- **AND** it SHALL preserve them for per-turn and accumulated usage reporting
- **AND** it SHALL NOT treat `total_tokens` as the current context occupancy

#### Scenario: Agents SDK usage is received

- **WHEN** usage includes `input_tokens`, `output_tokens`, `input_tokens_details`, or `output_tokens_details`
- **THEN** Deepy SHALL normalize those fields into `TokenUsage`
- **AND** it SHALL preserve them for per-turn and accumulated usage reporting
- **AND** it SHALL NOT let a smaller latest-turn input token value reduce the effective session context tokens for an unchanged or appended session

### Requirement: Context And Compact Display

Deepy SHALL show context pressure as an estimate for when automatic compaction will occur, using effective session context tokens rather than latest-turn API cost.

#### Scenario: A model turn completes

- **WHEN** Deepy receives usage for one or more model requests in a user turn
- **THEN** it SHALL display per-turn usage details after the response
- **AND** it SHALL update the bottom context status with current estimated context, compact threshold, total context window, and percentage
- **AND** the context status SHALL be based on effective replayable session context tokens
- **AND** the context status SHALL NOT decrease merely because the latest user turn used fewer API input tokens than the previous turn

#### Scenario: A session is compacted

- **WHEN** manual or automatic compaction rewrites a session
- **THEN** Deepy SHALL update context status using the compacted summary tokens plus preserved recent context
- **AND** it SHALL NOT report context usage as zero unless the session is empty
- **AND** this explicit rewrite MAY reduce effective context tokens

#### Scenario: Pending context exists

- **WHEN** session messages have been appended after the latest precise usage checkpoint
- **THEN** Deepy SHALL include pending estimated tokens in context status when useful
- **AND** it SHALL make clear that the context count is estimated

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
