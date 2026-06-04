## Why

Stable terminal UI currently relies on POSIX-only cursor-row probing to decide
whether a submitted prompt was rendered on the terminal's final row and needs
extra scroll space before model or local-command status starts. This works in
macOS terminal testing, but on Windows the cursor probe cannot run, so the
bottom-anchor branch is skipped and transcript output may remain stuck against
the runtime status row.

## What Changes

- Make stable terminal UI detect bottom-row prompt submission on Windows
  terminals instead of treating the cursor position as unknown.
- Preserve the existing macOS/Linux ANSI cursor report path and visible behavior.
- Keep the fix scoped to stable prompt-toolkit/Rich terminal UI; experimental
  Textual TUI behavior is unchanged.
- Add regression coverage for Windows cursor-row detection and bottom-anchor
  decision behavior.
- Add a conservative fallback only if Windows cursor position cannot be read
  from the console API.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: Stable terminal UI must preserve the bottom-anchor scroll
  behavior on Windows when submitted prompt text reaches the terminal bottom.

## Impact

- Affected code:
  - `src/deepy/ui/terminal.py`
  - `tests/test_terminal_ui.py`
- Affected systems:
  - Windows Terminal / PowerShell stable UI sessions
  - Existing macOS/Linux stable UI bottom-status behavior
- No public API, configuration, dependency, or session format changes are
  expected.
