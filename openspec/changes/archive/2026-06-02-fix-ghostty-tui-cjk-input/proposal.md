## Why

Ghostty can emit Chinese IME commits through Kitty keyboard protocol associated-text sequences that Textual 8.2.6 does not parse. In the Textual TUI this leaks raw CSI-u text such as `[32;;20320:22909u` into the prompt, making Chinese input unusable in Ghostty.

## What Changes

- Update the Textual dependency to a version that exposes the Kitty keyboard protocol disable switch.
- Disable Textual's Kitty keyboard protocol by default before importing Textual in the `deepy tui` startup path, so Ghostty falls back to normal UTF-8 text input.
- Preserve an environment-variable override for users who prefer enhanced keyboard protocol behavior.
- Remove stale prompt-level keyboard protocol naming left over from the earlier workaround.
- Add focused regression coverage for the Ghostty/Kitty associated-text sequence shape and the pre-import startup guard.

## Capabilities

### New Capabilities

### Modified Capabilities

- `experimental-textual-tui`: The Textual TUI must avoid corrupting CJK IME input in Ghostty by disabling the incompatible enhanced keyboard protocol path before Textual starts.

## Impact

- `pyproject.toml` and `uv.lock` Textual dependency resolution.
- `src/deepy/tui/runner.py` TUI startup environment setup before Textual imports.
- `src/deepy/tui/widgets.py` cleanup of stale handler naming.
- Focused tests in `tests/test_tui_app.py` and/or settings/dependency tests.
