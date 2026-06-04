## Why

Deepy 0.2.3 introduced a custom terminal-bottom status overlay that reserves
both a runtime status line and a prompt footer line during model and
local-command execution. Keeping the prompt footer fixed during active output
adds visual weight and can make transcript rendering feel less consistent, while
the single runtime status line is still useful for live progress.

## What Changes

- Remove the second fixed prompt-footer row from the runtime overlay.
- Keep a single fixed terminal-bottom runtime status line while a model turn or
  local command is running.
- Clear the runtime status line when the work completes.
- Keep the compact structured prompt footer, including current text such as
  `newline: ctrl+j`.
- Keep the 0.2.3 footer content model and concise labels such as
  `model deepseek-v4-pro[max]`, `[AGENTS.md]`, `mcp N`, and `ctx ...`.
- Keep thinking transcript output as realtime normal transcript output, not as
  footer content.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Runtime progress display reserves only one terminal-bottom
  runtime status line during active work; it no longer fixes the structured
  prompt footer to a second bottom row.

## Impact

- Affected code:
  - `src/deepy/ui/terminal.py`
  - `tests/test_terminal_ui.py`
- Not affected:
  - prompt toolbar help text
  - `StatusFooter` data model
  - status footer labels and segment styling
  - release/version metadata
- No new runtime dependencies.
