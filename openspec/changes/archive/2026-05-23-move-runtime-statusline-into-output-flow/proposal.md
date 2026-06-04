## Why

The stable terminal UI runtime status line still uses a fixed terminal-bottom
overlay, which can corrupt layout because it competes with prompt-toolkit's
bottom toolbar, submitted multiline prompt cleanup, AskUserQuestion continuation
turns, and platform-specific terminal cursor handling.

Moving the runtime status line into the normal output flow removes the competing
bottom owner while preserving the existing runtime status wording.

## What Changes

- Render model-turn and local-command runtime status lines as transient normal
  output-flow lines instead of fixed terminal-bottom overlays.
- Keep the runtime status text content unchanged, including elapsed time,
  interrupt hint, tool/local-command detail, and payload text.
- Remove the runtime status line's terminal scroll-region ownership, bottom-row
  reservation, and related one/two-line anchoring behavior.
- Revert the submitted multiline prompt and AskUserQuestion continuation anchor
  handling that only exists to protect the fixed bottom runtime row.
- Revert the POSIX and Windows cursor-row probing/fallback logic that only
  exists to decide whether bottom runtime status anchoring is needed.
- Render output-flow runtime status lines with segment-level foreground styling
  rather than a full-line background color.
- Preserve prompt-toolkit bottom toolbar behavior for the input phase; runtime
  status rendering must not take ownership of the terminal bottom row.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: Change model-turn and local-command runtime status from
  fixed terminal-bottom overlay behavior to transient normal output-flow
  behavior with segmented foreground styling.

## Impact

- Affected stable terminal UI code:
  - `src/deepy/ui/terminal.py`
  - related terminal UI tests in `tests/test_terminal_ui.py`
- Potentially affected docs or website UI demonstration surfaces:
  - `README.md`
  - `index.html`
  - `docs/deepy-ui-and-tui.md`
- No model prompt, tool schema, session history, or public CLI command changes
  are intended.
