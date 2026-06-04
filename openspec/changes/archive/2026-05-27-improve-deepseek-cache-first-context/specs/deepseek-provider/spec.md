## ADDED Requirements

### Requirement: DeepSeek Cache Prefix Snapshot
Deepy SHALL compute a deterministic cache-prefix snapshot for DeepSeek model
requests before invoking the OpenAI Agents SDK.

#### Scenario: DeepSeek model request is prepared
- **WHEN** Deepy prepares a model request for provider `deepseek`
- **THEN** it SHALL compute a cache-prefix snapshot from the stable request
  components Deepy controls
- **AND** the snapshot SHALL include system instructions, ordered built-in tool
  schemas, ordered MCP tool schemas, model id, DeepSeek reasoning settings,
  model settings that affect request shape, and stable skill/rule/prompt blocks
- **AND** Deepy SHALL persist the snapshot fingerprint with the active session
  metadata

#### Scenario: Stable prefix is unchanged
- **WHEN** two consecutive DeepSeek turns use identical cache-prefix snapshot
  components
- **THEN** Deepy SHALL reuse the same cache-prefix fingerprint
- **AND** it SHALL NOT record a prefix-change cache break for the second turn

#### Scenario: Prefix component changes
- **WHEN** any cache-prefix snapshot component changes between DeepSeek turns
- **THEN** Deepy SHALL compute a different cache-prefix fingerprint
- **AND** it SHALL record a cache break reason that identifies the changed
  component category

### Requirement: DeepSeek SDK Request Shape Diagnostics
Deepy SHALL provide a diagnostic path for validating cache-prefix assumptions
against the request shape produced through the OpenAI Agents SDK.

#### Scenario: Diagnostic capture is enabled in tests
- **WHEN** provider request-shape diagnostics are enabled by tests or explicit
  developer tooling
- **THEN** Deepy SHALL expose the canonical cache-prefix snapshot and the SDK
  request-shape fields needed to compare prefix ordering
- **AND** it SHALL omit API keys, authorization headers, and secret-bearing
  values from captured diagnostics

#### Scenario: Normal user session runs
- **WHEN** a normal Deepy session sends a provider request
- **THEN** Deepy SHALL NOT log full provider payloads by default
- **AND** it SHALL NOT print or persist API keys

### Requirement: DeepSeek Cache-Aligned Auxiliary Folding
Deepy SHALL keep context folding and compaction auxiliary requests aligned with
the active DeepSeek conversation model and model settings.

#### Scenario: DeepSeek compaction summary is requested
- **WHEN** Deepy creates a summary or fold request for a DeepSeek session
- **THEN** it SHALL use the active conversation DeepSeek model
- **AND** it SHALL use the active conversation DeepSeek model settings
- **AND** it SHALL request usage metadata through those model settings
- **AND** it SHALL preserve provider-side storage disabling through those model
  settings

#### Scenario: Active conversation uses reasoning
- **WHEN** the active DeepSeek conversation uses reasoning mode `high` or `max`
- **AND** Deepy creates a compaction summary request
- **THEN** the summary request SHALL keep the active DeepSeek reasoning setting
- **AND** it SHALL NOT switch to a separate auxiliary model

#### Scenario: Non-DeepSeek provider compacts context
- **WHEN** Deepy creates a summary or fold request for a provider other than
  official DeepSeek
- **THEN** it SHALL use provider-safe compaction settings
- **AND** it SHALL NOT assume DeepSeek cache behavior is available
