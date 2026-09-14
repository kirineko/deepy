# model-context-budget Specification

## Purpose
Define model-specific context and output budgets so every request, summary and tool continuation respects the selected model and makes uncertainty visible.

## Requirements

### Requirement: Model Limit Evidence
Deepy SHALL distinguish documented model limits, conservative runtime limits and unverified proxy limits for each supported provider/model/API combination.

#### Scenario: Model has only a nominal window
- **WHEN** official documentation reports 1M without an established exact token count
- **THEN** Deepy SHALL use a conservative 1,000,000-token runtime window and label it as conservative
- **AND** it SHALL NOT claim 1,048,576 is verified from that notation

#### Scenario: CLI Proxy models
- **WHEN** the selected model is one of the five supported CLI Proxy models
- **THEN** Deepy SHALL record the OpenAI 1,050,000 context and 128,000 output reference limits
- **AND** it SHALL distinguish those from the unverified proxy limits and apply any smaller configured cap

### Requirement: Complete Request Budget
Deepy SHALL check the complete target-model request before generation and each tool continuation.

#### Scenario: History has an older usage checkpoint
- **WHEN** new input, tool results or prompt/tool definitions exist after a checkpoint
- **THEN** the budget SHALL include them together with replayed history and system/tool overhead exactly once
- **AND** image data SHALL be estimated as image input rather than tokenized as base64 prose

#### Scenario: Tool schemas contain union types
- **WHEN** a built-in or MCP tool schema has an array-valued type or a property named type
- **THEN** the estimator SHALL count the complete schema without treating its type value as an image discriminator or failing before the request

#### Scenario: Input and output reserve approach the window
- **WHEN** estimated input reaches the configured ratio or input plus the total output-and-safety reserve reaches the effective window
- **THEN** Deepy SHALL prepare bounded compaction and recheck the resulting request before sending
- **AND** it SHALL count output reserve only once and expose a recoverable error if the request still cannot fit

#### Scenario: Continuation cannot fit
- **WHEN** a tool result makes the next request exceed its budget
- **THEN** Deepy SHALL preserve executed tool results and prepare at a legal tool boundary or stop recoverably
- **AND** it SHALL NOT automatically repeat tool side effects

### Requirement: Purpose-Specific Output Budgets
Deepy SHALL distinguish a model's maximum output from the output requested for each purpose.

#### Scenario: Request purpose is resolved
- **WHEN** main, subagent, compaction or suggestion requests are built
- **THEN** each SHALL use its actual model's limits and an explicit output budget within those limits
- **AND** suggestions SHALL retain their fixed models and thinking settings

#### Scenario: Independent auxiliary usage
- **WHEN** search or suggestion requests consume tokens
- **THEN** their usage SHALL NOT increase the main conversation's context occupancy
- **AND** their existing separate usage accounting SHALL remain available
