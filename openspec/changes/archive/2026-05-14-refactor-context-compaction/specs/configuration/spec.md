## ADDED Requirements

### Requirement: Context Compaction Configuration
Deepy SHALL provide TOML configuration for the new canonical context compaction policy.

#### Scenario: Default compaction config is loaded
- **WHEN** Deepy loads config without explicit compaction preservation or reserved context values
- **THEN** it SHALL use default values for reserved context tokens and recent context preservation
- **AND** `window_tokens` and `compact_trigger_ratio` SHALL feed the canonical auto compact policy

#### Scenario: Reserved context tokens are configured
- **WHEN** Deepy loads `[context].reserved_context_tokens`
- **THEN** it SHALL use that value when deciding whether automatic compaction is required
- **AND** invalid non-positive values SHALL fall back to the default

#### Scenario: Recent message preservation is configured
- **WHEN** Deepy loads `[context].compact_preserve_recent_messages`
- **THEN** it SHALL use that value when selecting recent messages to keep after compaction
- **AND** invalid non-positive values SHALL fall back to the default

#### Scenario: Recent token preservation is configured
- **WHEN** Deepy loads `[context].compact_preserve_recent_tokens`
- **THEN** it SHALL use that value as an optional token budget for preserved recent context
- **AND** invalid non-positive values SHALL be ignored

#### Scenario: Config is shown
- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include resolved compaction policy values
- **AND** it SHALL not present deprecated compact threshold aliases as authoritative policy values

#### Scenario: Removed compact threshold config is present
- **WHEN** Deepy loads a legacy `compact_prompt_token_threshold` field from an old config file
- **THEN** Deepy SHALL ignore the field entirely
- **AND** it SHALL NOT expose the removed field as part of the resolved runtime config
