## Why

The stable terminal UI can occasionally render the transient runtime bottom status incorrectly when tool parameters or local commands are long. The failure is visible as the spinner and elapsed-time prefix being pushed out or corrupted, while users still need meaningful command text to remain visible.

## What Changes

- Stabilize the one-line runtime bottom status so spinner, elapsed time, and interrupt affordance remain visible whenever terminal width allows.
- Treat runtime status content as prioritized segments instead of one undifferentiated string.
- Sanitize tool and command status payloads before writing them to the terminal-bottom row so embedded newlines, carriage returns, tabs, ANSI escape sequences, or other control characters cannot break the single-line display.
- Keep local command and shell tool command text visible, but constrain it to the remaining width with tail truncation so the command prefix remains intact.
- Preserve concise tool labels and payload summaries without allowing large generated arguments to wrap, scroll, or displace the protected runtime prefix.
- No breaking changes to CLI commands, session data, provider behavior, or tool protocol payloads.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Tighten the stable terminal UI contract for transient runtime bottom status fitting, payload sanitization, and command visibility under long parameters.

## Impact

- Affected code is expected to be concentrated in `src/deepy/ui/terminal.py` and the tool-summary formatting boundary in `src/deepy/ui/message_view.py` if shared helpers are needed.
- Tests should focus on `tests/test_terminal_ui.py` and any existing message-view tests that cover tool parameter summaries.
- No new runtime dependencies are expected.
