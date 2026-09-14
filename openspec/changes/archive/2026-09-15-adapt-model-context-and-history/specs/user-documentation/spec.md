
## ADDED Requirements

### Requirement: Model Context And History Documentation
Deepy SHALL document model-specific windows, output budgets and history migration consistently in English and Chinese.

#### Scenario: Users configure or switch models
- **WHEN** users consult the provider and context documentation
- **THEN** it SHALL distinguish official nominal limits, conservative values and unverified proxy limits, explain overrides and output reserve, and show history-preserving model switching
- **AND** it SHALL describe /compact --for-model, image-summary information loss, usage attribution and failure recovery
- **AND** it SHALL not claim maximum-context live validation from short smoke tests
