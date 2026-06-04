## ADDED Requirements

### Requirement: Manual Session Compaction
Deepy SHALL provide a durable session compaction operation that replaces older active session history with a model-generated summary while preserving recent context.

#### Scenario: Active session is compacted manually
- **WHEN** a user requests compaction for an active session
- **THEN** Deepy SHALL generate a structured summary from older session items
- **AND** it SHALL preserve configured recent session items after the summary
- **AND** it SHALL rewrite the active session so `/resume` continues from the compacted context

#### Scenario: Manual compaction includes a focus instruction
- **WHEN** a user requests compaction with an additional focus instruction
- **THEN** Deepy SHALL include that instruction in the compaction prompt
- **AND** the generated summary SHALL prioritize the requested focus without dropping current task state

#### Scenario: Session has too little history to compact
- **WHEN** manual compaction is requested for a session with no eligible older history
- **THEN** Deepy SHALL leave the active session unchanged
- **AND** it SHALL report that there is no context to compact

### Requirement: Legacy Context Logic Retirement
Deepy SHALL remove the old placeholder compaction and silent model-input trimming behavior from the active context management path.

#### Scenario: Old placeholder compaction entry point is called
- **WHEN** an internal caller requests session compaction through the existing session manager API
- **THEN** Deepy SHALL delegate to the new durable compaction service
- **AND** it SHALL NOT clear history and replace it with a static placeholder message

#### Scenario: Model input is prepared for a turn
- **WHEN** Deepy prepares session history for an Agents SDK model run
- **THEN** the preparation step SHALL NOT silently drop older persisted items as a substitute for compaction
- **AND** any required compaction SHALL have already completed through the durable pre-run compaction flow

#### Scenario: Context is too large after required compaction fails
- **WHEN** Deepy cannot compact a session that exceeds policy
- **THEN** it SHALL stop before the model request
- **AND** it SHALL report a clear context compaction error instead of sending a silently trimmed request

### Requirement: Compaction Recoverability
Deepy SHALL preserve the pre-compaction session history before replacing the active session.

#### Scenario: Compaction succeeds
- **WHEN** Deepy successfully generates a compaction summary and replacement history
- **THEN** it SHALL rotate or archive the original session JSONL before writing the replacement
- **AND** it SHALL update the active session index after the replacement is written

#### Scenario: Summary generation fails
- **WHEN** the compaction model call fails
- **THEN** Deepy SHALL leave the original active session JSONL unchanged
- **AND** it SHALL report the compaction failure to the caller

#### Scenario: Replacement write fails
- **WHEN** Deepy has archived the original session but cannot write the replacement history
- **THEN** it SHALL restore the original session JSONL when possible
- **AND** it SHALL NOT leave the active session in a partially compacted state

### Requirement: Automatic Session Compaction
Deepy SHALL automatically compact the active session before a model turn when context pressure exceeds configured policy.

#### Scenario: Ratio trigger is reached
- **WHEN** the effective active context tokens are greater than or equal to the configured compact trigger ratio of the context window
- **THEN** Deepy SHALL run durable session compaction before sending the next model request
- **AND** the model request SHALL use the compacted session history

#### Scenario: Reserved context trigger is reached
- **WHEN** the effective active context tokens plus the configured reserved context tokens are greater than or equal to the context window
- **THEN** Deepy SHALL run durable session compaction before sending the next model request
- **AND** the model request SHALL use the compacted session history

#### Scenario: Automatic compaction fails
- **WHEN** automatic compaction is required but fails
- **THEN** Deepy SHALL leave the active session unchanged
- **AND** it SHALL stop the model turn with a clear compaction error instead of silently sending an oversized request

### Requirement: Pending Context Token Accounting
Deepy SHALL account for messages appended after the latest precise usage update when deciding context pressure.

#### Scenario: Usage update is recorded
- **WHEN** a model turn returns precise context usage
- **THEN** Deepy SHALL store that usage as the latest precise token checkpoint for the session
- **AND** it SHALL reset pending token estimate for messages covered by that usage

#### Scenario: Messages are appended after usage
- **WHEN** user, assistant, or tool messages are appended after the latest precise usage checkpoint
- **THEN** Deepy SHALL add estimated tokens for those messages to the session pending token estimate
- **AND** automatic compaction SHALL use precise checkpoint tokens plus pending estimated tokens

#### Scenario: Session is restored
- **WHEN** Deepy restores a session with token checkpoint metadata
- **THEN** it SHALL reconstruct the effective active token estimate from the latest checkpoint and messages appended after that checkpoint

## MODIFIED Requirements

### Requirement: Context And Compact Display
Deepy SHALL show context pressure as an estimate for when automatic compaction will occur, including compacted active tokens, pending estimated tokens, reserved context budget, total context window, compact threshold, and percentage.

#### Scenario: A model turn completes
- **WHEN** Deepy receives usage for one or more model requests in a user turn
- **THEN** it SHALL display per-turn usage details after the response
- **AND** it SHALL update the bottom context status with current estimated context, total context window, compact threshold, reserved context budget, and percentage

#### Scenario: A session is compacted
- **WHEN** manual or automatic compaction rewrites a session
- **THEN** Deepy SHALL update context status using the compacted summary tokens plus preserved recent context
- **AND** it SHALL NOT report context usage as zero unless the session is empty

#### Scenario: Pending context exists
- **WHEN** session messages have been appended after the latest precise usage checkpoint
- **THEN** Deepy SHALL include pending estimated tokens in context status
- **AND** it SHALL make clear that the context count is estimated
