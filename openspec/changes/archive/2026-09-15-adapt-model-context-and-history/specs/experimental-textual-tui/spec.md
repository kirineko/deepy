## MODIFIED Requirements

### Requirement: Textual Provider Model Selection
The experimental Textual TUI SHALL expose the same provider-aware model and
thinking settings as the stable terminal UI.

#### Scenario: User opens Textual model command without arguments
- **WHEN** a user invokes `/model` in the experimental TUI without arguments
- **THEN** the TUI SHALL present provider choices `DeepSeek`, `MiMo`, `Kimi`, and `CLI Proxy`
- **AND** it SHALL present only models supported by the selected provider
- **AND** it SHALL present only thinking choices supported by the selected provider

#### Scenario: User selects Textual provider model settings
- **WHEN** a user completes provider, model, and thinking selection at a safe idle boundary in the experimental TUI
- **THEN** the TUI SHALL merge the selected profile settings and active selection into TOML without changing other profiles
- **AND** it SHALL reload in-memory settings for subsequent model turns
- **AND** it SHALL show a concise confirmation with provider, model, and thinking mode

#### Scenario: User resets config in Textual TUI
- **WHEN** a user invokes `/reset` in the experimental TUI
- **THEN** the reset form SHALL allow selecting provider `DeepSeek`, `MiMo`, `Kimi`, or `CLI Proxy`
- **AND** the model choices SHALL match the selected provider
- **AND** the base URL SHALL default to the selected provider's default base URL
- **AND** the thinking choices SHALL match the selected provider

#### Scenario: User cancels Textual provider selection
- **WHEN** a user cancels provider, model, thinking, or reset selection before saving
- **THEN** the TUI SHALL preserve the existing saved settings
- **AND** it SHALL keep current in-memory settings unchanged

#### Scenario: Existing provider configuration is edited
- **WHEN** the user edits a provider through the Textual configuration surface
- **THEN** the form SHALL restore that profile's saved model, reasoning and URL
- **AND** blank password input SHALL retain its existing saved key
- **AND** runtime environment overrides SHALL NOT be serialized into saved credentials
- **AND** ordinary profile editing SHALL preserve unrelated settings and SHALL NOT act as full reset

#### Scenario: Model switch is requested during active work
- **WHEN** generation, tool execution, approval or subagent work is unresolved
- **THEN** the TUI SHALL reject the switch with recovery guidance and leave current settings unchanged

#### Scenario: Selected model retains earlier history
- **WHEN** the selected model changes while the session has earlier history
- **THEN** the TUI SHALL preserve the session and draft, show the target window and history readiness, and validate replay before generation
- **AND** it SHALL not report old-model usage as precise target-model occupancy

#### Scenario: Textual history migration recovery
- **WHEN** history exceeds the target budget or contains incompatible images
- **THEN** the TUI SHALL provide the same bounded preparation, /compact --for-model opt-in and cancellation behavior as Classic UI
- **AND** failure SHALL preserve originals and pending input
