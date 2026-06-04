## MODIFIED Requirements

### Requirement: DeepSeek Cache Prefix Snapshot
Deepy SHALL compute a deterministic cache-prefix snapshot for DeepSeek model
requests before invoking the OpenAI Agents SDK.

#### Scenario: DeepSeek model request is prepared
- **WHEN** Deepy prepares a model request for provider `deepseek`
- **THEN** it SHALL compute a cache-prefix snapshot from the stable request
  components Deepy controls
- **AND** the snapshot SHALL include system instructions, ordered built-in tool
  schemas including the v3 `Read`, `Write`, and `Update` definitions, ordered
  MCP tool schemas, model id, DeepSeek reasoning settings, model settings that
  affect request shape, and stable skill/rule/prompt blocks
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

#### Scenario: File tool surface changes
- **WHEN** Deepy upgrades from the v2 file tool surface to the v3 `Read`,
  `Write`, and `Update` surface
- **THEN** Deepy SHALL treat the changed built-in tool schema set as an
  intentional prefix change
- **AND** subsequent unchanged turns SHALL reuse the new v3 prefix snapshot
