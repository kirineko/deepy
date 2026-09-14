## MODIFIED Requirements

### Requirement: Context Compaction Configuration

Deepy SHALL provide TOML configuration for the canonical context compaction
policy.

#### Scenario: Default compaction config is loaded

- **WHEN** Deepy loads config without explicit compaction preservation or reserved
  context values
- **THEN** it SHALL use default values for reserved context tokens and recent
  context preservation
- **AND** the resolved model window and `compact_trigger_ratio` SHALL feed the canonical
  auto compact policy; omitted `window_tokens` SHALL follow the selected model

#### Scenario: Reserved context tokens are configured

- **WHEN** Deepy loads `[context].reserved_context_tokens`
- **THEN** it SHALL use that value as a total reserve floor, combining it with output and estimation allowance by maximum rather than adding the output budget twice
- **AND** invalid non-positive values SHALL fall back to the default

#### Scenario: Recent message preservation is configured

- **WHEN** Deepy loads `[context].compact_preserve_recent_messages`
- **THEN** it SHALL use that value when selecting recent messages to keep after
  compaction
- **AND** invalid non-positive values SHALL fall back to the default

#### Scenario: Recent token preservation is configured

- **WHEN** Deepy loads `[context].compact_preserve_recent_tokens`
- **THEN** it SHALL use that value as an optional token budget for preserved
  recent context
- **AND** invalid non-positive values SHALL be ignored

#### Scenario: Config is shown

- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include resolved compaction policy values, target model limits, their sources and separately identified explicit overrides
- **AND** it SHALL not present removed compact threshold aliases as authoritative
  policy values

#### Scenario: Removed compact threshold config is present

- **WHEN** Deepy loads a legacy `compact_prompt_token_threshold` field from an
  old config file
- **THEN** Deepy SHALL ignore the field entirely
- **AND** it SHALL NOT expose the removed field as part of the resolved runtime
  config

## ADDED Requirements

### Requirement: Model Limit Overrides
Deepy SHALL allow provider/model-specific context caps and request output budgets without changing other profiles.

#### Scenario: Overrides are resolved
- **WHEN** limits are loaded
- **THEN** the effective window SHALL be the minimum of the model runtime limit, any explicit global context.window_tokens cap and any providers.<provider>.model_limits.<model>.context_window_tokens cap
- **AND** absent caps SHALL follow the catalog rather than a universal fixed window
- **AND** model max_output_tokens overrides SHALL configure the requested output budget within the model output limit

#### Scenario: Invalid override or failed save
- **WHEN** a limit is unknown, non-positive, exceeds a known model maximum or cannot fit output and safety reserve, or a write fails
- **THEN** Deepy SHALL reject the operation without changing persisted or active settings

#### Scenario: Resolved configuration is displayed
- **WHEN** config show or doctor reports limits
- **THEN** it SHALL identify the selected model, effective limits, explicit overrides and unverified/conservative sources
- **AND** merely loading or displaying configuration SHALL NOT persist inferred limits
