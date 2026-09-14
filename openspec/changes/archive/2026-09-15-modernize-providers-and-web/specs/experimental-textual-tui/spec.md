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
- **WHEN** a user completes provider, model, and thinking selection in the experimental TUI
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
