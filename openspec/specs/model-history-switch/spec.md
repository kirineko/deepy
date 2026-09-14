# model-history-switch Specification

## Purpose
Preserve conversation history and recoverable user work while preparing a valid replay for a newly selected model with different limits or capabilities.

## Requirements

### Requirement: Non-Destructive Target History
Deepy SHALL continue the same session after model selection while preserving original messages, image attachments and complete tool-call/result groups.

#### Scenario: Provider or model changes
- **WHEN** a user selects another model
- **THEN** Deepy SHALL prepare a target-compatible replay view without deleting original history
- **AND** it SHALL preserve user messages, final answers and valid tool continuations
- **AND** it SHALL isolate unsupported reasoning, signatures and encrypted items by source and target compatibility
- **AND** it SHALL remove foreign or unproven server item IDs from the replay copy while retaining tool call_id pairing and the original records

#### Scenario: Model is switched back or session resumed
- **WHEN** an earlier model is selected again or a session is resumed
- **THEN** Deepy SHALL revalidate the replay view against current history, prompt definitions and target limits
- **AND** it SHALL reuse only a still-valid prepared view, without silently restoring an oversized older context

### Requirement: Safe Selection Boundary
Deepy SHALL change the active model only at an idle boundary that has no unresolved model turn, tool execution, approval or subagent work.

#### Scenario: Work is in progress
- **WHEN** a model switch is requested during active work
- **THEN** Deepy SHALL leave current settings unchanged and explain how to finish or cancel before retrying

#### Scenario: Selection saved but history not ready
- **WHEN** the user saves a selection at an idle boundary
- **THEN** Deepy SHALL mark target history as requiring validation before the next model request
- **AND** merely browsing model choices SHALL NOT start paid summarization

### Requirement: Bounded History Migration
Deepy SHALL validate summarization requests against the summarizing model's own budget and commit a replacement active view only after successful target validation.

#### Scenario: History exceeds the target window
- **WHEN** target history cannot fit
- **THEN** Deepy SHALL use budgeted summaries of complete history groups and preserve task constraints, outstanding work and relevant results
- **AND** it SHALL NOT submit an oversized full history merely to ask the target model to summarize it
- **AND** source-model fallback SHALL be limited to the session's last successful configured source model and identify that model before calling it

#### Scenario: History cannot be summarized safely
- **WHEN** an indivisible history group cannot fit any eligible summary request or no eligible model is available
- **THEN** Deepy SHALL stop with recovery guidance while preserving history and the draft

#### Scenario: Migration is interrupted or becomes stale
- **WHEN** summarization fails, is cancelled, hits its 32-request or per-request 60-second bound, or history changes before commit
- **THEN** Deepy SHALL retain the prior active view, originals and pending input without sending the unready target request
- **AND** it SHALL retain usage for completed summary requests without automatically retrying them

### Requirement: Explicit Image History Reduction
Deepy SHALL block original image history for text-only targets unless the user explicitly chooses a text-summary path.

#### Scenario: Image history meets a text-only target
- **WHEN** existing image history is incompatible with the selected model
- **THEN** Deepy SHALL explain the incompatibility and offer switching back, a new text session or explicit text summarization
- **AND** it SHALL NOT silently remove images or manufacture descriptions

#### Scenario: User chooses a text summary
- **WHEN** the user explicitly requests a text-only view of image history
- **THEN** an eligible image-capable model SHALL produce that summary within its budget
- **AND** Deepy SHALL preserve original attachments and label the active view as a potentially lossy text summary

### Requirement: Encoded Summary Request Budget
Deepy SHALL check encoded JSON size as well as token and image-count limits when planning summary batches, including summary instructions, focus, todo context, and tool definitions with serialization headroom.

#### Scenario: Independent images exceed the encoded request limit
- **WHEN** individually valid image history groups exceed 32 MiB when combined in a summary request
- **THEN** Deepy SHALL split them into smaller summary batches before invoking the summarizer
- **AND** all dispatched summary batches SHALL stay within the encoded request limit

#### Scenario: Indivisible group exceeds the encoded request limit
- **WHEN** a complete tool group cannot fit within the encoded summary request limit
- **THEN** Deepy SHALL reject that group without invoking the summarizer for it and preserve the original history
