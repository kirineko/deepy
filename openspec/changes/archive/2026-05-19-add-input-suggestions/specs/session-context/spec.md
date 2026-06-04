## ADDED Requirements

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
