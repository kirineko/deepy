## Why

The experimental Textual TUI still uses and documents Shift+Enter for multiline input, while Deepy's stable terminal UI contract uses Ctrl+J. This creates inconsistent muscle memory and preserves a shortcut that previous terminal testing found unreliable.

## What Changes

- Change the experimental Textual TUI prompt newline shortcut from Shift+Enter to Ctrl+J.
- Align TUI startup/help copy with the stable UI wording for newline insertion.
- Update TUI regression tests so Ctrl+J inserts a newline and Enter still submits.
- Update user-facing comparison documentation so TUI newline behavior is no longer described as a design difference.
- Remove remaining TUI-facing Shift+Enter newline requirements and guidance.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `experimental-textual-tui`: Align Textual-native prompt newline insertion with the stable terminal UI Ctrl+J shortcut.

## Impact

- Affected code: `src/deepy/tui/widgets.py`, `src/deepy/tui/app.py`.
- Affected tests: `tests/test_tui_app.py` and any focused TUI help/keybinding assertions.
- Affected docs/specs: `docs/deepy-ui-and-tui.md`, `openspec/specs/experimental-textual-tui/spec.md`.
- No dependency, CLI API, model API, or session format changes.
