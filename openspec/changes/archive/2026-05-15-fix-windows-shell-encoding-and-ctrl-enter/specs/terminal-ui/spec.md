## MODIFIED Requirements

### Requirement: Prompt Input Behavior

Deepy SHALL provide ergonomic multiline terminal input.

#### Scenario: User submits input

- **WHEN** a user presses Enter
- **THEN** Deepy SHALL submit the current prompt

#### Scenario: User inserts a newline

- **WHEN** a user presses Ctrl+J
- **THEN** Deepy SHALL insert a newline into the prompt
- **AND** it SHALL NOT submit the prompt

#### Scenario: User exits with Ctrl+D

- **WHEN** a user presses Ctrl+D once
- **THEN** Deepy SHALL ask for a second Ctrl+D confirmation
- **WHEN** the user presses Ctrl+D again
- **THEN** Deepy SHALL exit cleanly

## REMOVED Requirements

### Requirement: Windows-Specific Newline Shortcut Behavior

**Reason**: Ctrl+J is no longer a Windows-specific fallback. It is the single
cross-platform newline shortcut. Separate Windows-only shortcut requirements are
unnecessary and would reintroduce platform-specific behavior.

**Migration**: Use Ctrl+J for multiline input on all platforms. Keep Enter for
submit. Shift+Enter and Ctrl+Enter are no longer supported newline shortcuts.
