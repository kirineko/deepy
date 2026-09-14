# input-suggestions Specification

## Purpose

Deepy offers cancellable, filtered input suggestions using fixed provider-local Responses models and reports their usage separately from conversation requests.

## Requirements

### Requirement: Input Suggestion Eligibility
Deepy SHALL generate input suggestions only for eligible interactive sessions
after completed model replies.

#### Scenario: Eligible turn completes
- **WHEN** an interactive model turn completes successfully
- **AND** the active session contains at least two assistant/model replies
- **AND** input suggestions are enabled
- **AND** no model turn, local command, prompt confirmation, or
  AskUserQuestion flow is active
- **THEN** Deepy SHALL request an input suggestion in the background

#### Scenario: Conversation is too early
- **WHEN** an interactive model turn completes
- **AND** the active session contains fewer than two assistant/model replies
- **THEN** Deepy SHALL NOT request an input suggestion

#### Scenario: Session is not interactive
- **WHEN** Deepy runs in non-interactive CLI, doctor, SDK, or headless mode
- **THEN** Deepy SHALL NOT request or display input suggestions

#### Scenario: Prompt is no longer idle
- **WHEN** a suggestion request is pending or a suggestion is visible
- **AND** the user starts typing, pastes content, submits a prompt, starts a
  local command, starts a model turn, or disables input suggestions
- **THEN** Deepy SHALL cancel the pending request when possible
- **AND** it SHALL clear the visible suggestion

### Requirement: Input Suggestion Generation
Deepy SHALL use a dedicated background prompt to predict the user's likely next
input from recent conversation context.

#### Scenario: Suggestion is requested
- **WHEN** Deepy requests an input suggestion
- **THEN** it SHALL send recent conversation context plus a suggestion-specific
  instruction to the suggestion model
- **AND** the instruction SHALL ask for the user's likely next input rather than
  an assistant action or explanation
- **AND** the request SHALL be best-effort and SHALL NOT block user input

#### Scenario: Explicit next-step hint exists
- **WHEN** the latest assistant reply contains an explicit next-step hint such
  as "type X" or "Tip: X"
- **THEN** the suggestion MAY extract the hinted user action as the suggestion
  if it passes quality filtering

#### Scenario: Generation fails
- **WHEN** the suggestion model call fails, times out, is cancelled, or returns
  an unusable response
- **THEN** Deepy SHALL suppress the suggestion without interrupting the
  interactive session

### Requirement: Input Suggestion Quality Filtering
Deepy SHALL suppress suggestions that are unlikely to be useful as direct user
input.

#### Scenario: Suggestion length is invalid
- **WHEN** a generated suggestion has fewer than two words, more than twelve
  words, at least one hundred characters, fewer than two CJK characters, or more
  than thirty CJK characters
- **THEN** Deepy SHALL suppress the suggestion
- **AND** slash commands and a small allowlist of common one-word commands MAY
  pass the minimum word filter

#### Scenario: Suggestion is not direct input
- **WHEN** a generated suggestion is evaluative, AI-voiced, a question, a meta
  comment, an error message, a prefixed label, multiple sentences, Markdown, or
  contains newlines
- **THEN** Deepy SHALL suppress the suggestion

#### Scenario: Suggestion passes filters
- **WHEN** a generated suggestion passes all quality filters
- **THEN** Deepy MAY display it as ghost text in the active prompt

### Requirement: Input Suggestion Acceptance
Deepy SHALL allow users to accept visible input suggestions without submitting
the prompt.

#### Scenario: User presses Tab
- **WHEN** an input suggestion is visible
- **AND** the input buffer is empty
- **AND** the user presses Tab
- **THEN** Deepy SHALL insert the suggestion into the input buffer
- **AND** it SHALL NOT submit the prompt
- **AND** it SHALL clear the visible suggestion

#### Scenario: User presses Right Arrow
- **WHEN** an input suggestion is visible
- **AND** the input buffer is empty
- **AND** the user presses Right Arrow
- **THEN** Deepy SHALL insert the suggestion into the input buffer
- **AND** it SHALL NOT submit the prompt
- **AND** it SHALL clear the visible suggestion

#### Scenario: User presses Enter
- **WHEN** an input suggestion is visible
- **AND** the input buffer is empty
- **AND** the user presses Enter
- **THEN** Deepy SHALL NOT accept the suggestion
- **AND** it SHALL preserve the normal Enter-to-submit behavior for the current
  prompt buffer

#### Scenario: Completion surface is active
- **WHEN** slash command completion or file mention completion is active
- **THEN** those completion surfaces SHALL keep their existing Tab and selection
  behavior
- **AND** input suggestion acceptance SHALL NOT override them

### Requirement: Input Suggestion Model
Deepy SHALL use a fixed provider-local Responses model for suggestions without exposing custom suggestion model configuration.

#### Scenario: Suggestion model call is created
- **WHEN** a suggestion request is created
- **THEN** Deepy SHALL use DeepSeek deepseek-flash with none, MiMo mimo-v2.5 with disabled, Kimi kimi-k3 with low, or CLI Proxy gpt-5.6-luna with none according to the active provider
- **AND** it SHALL use that provider credentials, request usage and disable storage

#### Scenario: Active model is changed
- **WHEN** the main model or reasoning changes within a provider
- **THEN** the suggestion model and reasoning SHALL remain fixed for that provider

#### Scenario: Provider changed
- **WHEN** the active provider changes
- **THEN** subsequent suggestions SHALL use the new provider fixed model without requiring another provider key

#### Scenario: User requests suggestion model customization
- **WHEN** a user attempts to configure a custom suggestion model
- **THEN** Deepy SHALL reject or ignore that customization and retain the fixed provider-local model

### Requirement: Input Suggestion Usage Accounting
Deepy SHALL account for input suggestion model usage separately from ordinary
model-turn usage.

#### Scenario: Suggestion usage is known
- **WHEN** an input suggestion model call returns token usage
- **THEN** Deepy SHALL record that usage in an input-suggestion-specific usage
  bucket
- **AND** it SHALL NOT merge that usage into the ordinary turn usage footer
- **AND** it SHALL NOT update latest request Context Window usage checkpoints

#### Scenario: Suggestion usage is displayed
- **WHEN** Deepy displays accumulated interactive usage that includes input
  suggestion calls
- **THEN** it SHALL label suggestion usage separately from ordinary model usage
- **AND** it SHALL identify the actual suggestion provider and model
