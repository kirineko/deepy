## 1. TUI Key Binding Behavior

- [x] 1.1 Change the main TUI prompt newline binding from Shift+Enter to Ctrl+J while keeping Enter submission unchanged.
- [x] 1.2 Change the TUI custom question text area newline binding from Shift+Enter to Ctrl+J while keeping Enter submission unchanged.
- [x] 1.3 Confirm slash suggestions, file mention suggestions, prompt history, and Ctrl+D exit behavior are unaffected by the binding change.

## 2. TUI Guidance And Documentation

- [x] 2.1 Update TUI startup guidance to advertise Ctrl+J for newline insertion.
- [x] 2.2 Update TUI `/help` keybinding text to advertise Ctrl+J and remove Shift+Enter newline guidance.
- [x] 2.3 Update `docs/deepy-ui-and-tui.md` so TUI newline behavior is documented as aligned with the stable UI.

## 3. Regression Tests

- [x] 3.1 Update the focused TUI prompt test to press Ctrl+J and verify a newline is inserted without submission.
- [x] 3.2 Add or update TUI assertions that startup/help text does not advertise Shift+Enter as the newline shortcut.
- [x] 3.3 Add or update custom question text area coverage so Ctrl+J inserts multiline custom-answer text and Enter submits.

## 4. Validation

- [x] 4.1 Run focused TUI tests covering prompt newline behavior and question custom text behavior.
- [x] 4.2 Run focused stable prompt input tests to confirm the existing prompt-toolkit Ctrl+J contract still passes.
- [x] 4.3 Run `openspec validate fix-tui-ctrl-j-newline --type change --strict`.
