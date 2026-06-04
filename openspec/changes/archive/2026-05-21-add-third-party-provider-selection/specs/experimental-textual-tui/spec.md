## ADDED Requirements

### Requirement: Textual Provider Model Selection
The experimental Textual TUI SHALL expose the same provider-aware model and
thinking settings as the stable terminal UI.

#### Scenario: User opens Textual model command without arguments
- **WHEN** a user invokes `/model` in the experimental TUI without arguments
- **THEN** the TUI SHALL present provider choices `DeepSeek`, `OpenRouter`, and `Xiaomi`
- **AND** it SHALL present only models supported by the selected provider
- **AND** it SHALL present only thinking choices supported by the selected provider

#### Scenario: User selects Textual provider model settings
- **WHEN** a user completes provider, model, and thinking selection in the experimental TUI
- **THEN** the TUI SHALL persist the selected settings to TOML
- **AND** it SHALL reload in-memory settings for subsequent model turns
- **AND** it SHALL show a concise confirmation with provider, model, and thinking mode

#### Scenario: User resets config in Textual TUI
- **WHEN** a user invokes `/reset` in the experimental TUI
- **THEN** the reset form SHALL allow selecting provider `DeepSeek`, `OpenRouter`, or `Xiaomi`
- **AND** the model choices SHALL match the selected provider
- **AND** the base URL SHALL default to the selected provider's default base URL
- **AND** the thinking choices SHALL match the selected provider

#### Scenario: User cancels Textual provider selection
- **WHEN** a user cancels provider, model, thinking, or reset selection before saving
- **THEN** the TUI SHALL preserve the existing saved settings
- **AND** it SHALL keep current in-memory settings unchanged

## MODIFIED Requirements

### Requirement: Textual App Shell
The experimental TUI SHALL use a Deepy-owned Textual app shell for layout,
navigation, live state, and command discovery.

#### Scenario: TUI starts in a project
- **WHEN** the experimental TUI starts
- **THEN** it SHALL show the Deepy identity, current project root, active provider,
  active model, thinking mode, session state, and experimental status
- **AND** it SHALL provide discoverable keyboard help for core actions

#### Scenario: Terminal width changes
- **WHEN** the terminal is resized
- **THEN** the TUI SHALL adapt transcript, prompt, footer, and detail panels to
  the available width
- **AND** text SHALL remain readable without incoherent overlap

#### Scenario: Theme is resolved
- **WHEN** the TUI starts with a saved `auto`, `dark`, or `light` UI theme
- **THEN** it SHALL resolve a Textual theme compatible with that setting
- **AND** transcript text, tool blocks, prompts, status, and diffs SHALL remain
  readable

### Requirement: Textual Command Surfaces
The experimental Textual TUI SHALL provide Textual-native command discovery and
auxiliary command surfaces while preserving slash command entry from the prompt.

#### Scenario: User opens command discovery
- **WHEN** a user opens command discovery in the experimental TUI
- **THEN** the TUI SHALL show available commands grouped by purpose
- **AND** each command SHALL include a concise label and description
- **AND** selecting a command SHALL either run it or open the appropriate
  Textual screen, modal, or form

#### Scenario: User types a slash command
- **WHEN** a user types `/` at the beginning of the TUI prompt
- **THEN** the TUI SHALL provide prompt-adjacent slash command suggestions
- **AND** selecting a suggestion SHALL insert the command without submitting
  unrelated prompt text

#### Scenario: Command is not implemented in TUI yet
- **WHEN** a user invokes a stable Deepy slash command that is not yet
  implemented in the experimental TUI
- **THEN** the TUI SHALL show a clear TUI-specific unsupported message
- **AND** it SHALL NOT silently ignore the command or start a model turn

#### Scenario: Model command is implemented in TUI
- **WHEN** a user invokes `/model` or `/reset` in the experimental TUI
- **THEN** the TUI SHALL use Textual-native provider, model, and thinking selection surfaces
- **AND** it SHALL NOT fall back to the stable prompt-toolkit picker
