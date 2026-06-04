## 1. Dependency And Startup Strategy

- [x] 1.1 Update the Textual dependency lock to a version with `TEXTUAL_DISABLE_KITTY_KEY`.
- [x] 1.2 Configure the TUI runner to disable Textual Kitty keyboard protocol before importing the Textual app, while preserving user overrides.

## 2. Prompt Cleanup And Tests

- [x] 2.1 Remove stale prompt-level keyboard-protocol naming from the Textual prompt widget.
- [x] 2.2 Add focused regression tests for Ghostty multi-codepoint associated-text parser behavior and the Deepy pre-import startup guard.

## 3. Validation

- [x] 3.1 Validate the OpenSpec change in strict mode.
- [x] 3.2 Run focused TUI tests and dependency checks affected by the change.
