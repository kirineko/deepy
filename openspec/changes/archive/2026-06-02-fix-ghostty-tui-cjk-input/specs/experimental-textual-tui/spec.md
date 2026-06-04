## ADDED Requirements

### Requirement: Ghostty CJK Input Compatibility
The experimental Textual TUI SHALL prevent Ghostty-specific Kitty keyboard protocol associated-text sequences from being inserted as literal prompt text during CJK IME input.

#### Scenario: Ghostty commits CJK text through associated-text keyboard protocol
- **WHEN** a user starts `deepy tui` in an environment where the terminal would otherwise emit Kitty keyboard protocol associated-text sequences for CJK IME commits
- **THEN** Deepy SHALL configure Textual startup before Textual is imported so the incompatible enhanced keyboard protocol path is disabled by default
- **AND** CJK prompt input SHALL be accepted through normal Textual text input rather than prompt-content replacement after insertion

#### Scenario: User explicitly opts into Textual Kitty keyboard protocol
- **WHEN** the user starts `deepy tui` with a preconfigured Textual keyboard-protocol environment override
- **THEN** Deepy SHALL preserve that explicit environment value
- **AND** it SHALL NOT overwrite the user's selected Textual keyboard protocol behavior
