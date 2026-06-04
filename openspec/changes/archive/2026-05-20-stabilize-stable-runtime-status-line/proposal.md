## Why

The stable terminal UI can show subtle bottom runtime-status corruption while
long-running tools such as WebSearch are active, especially around spinner and
elapsed-time refreshes. The status line should remain a single, clean,
replace-in-place terminal row regardless of tool name length, CJK query text, or
concurrent stream output.

## What Changes

- Make bottom runtime-status updates use display-cell-aware truncation and
  padding instead of Python character counts.
- Serialize terminal-bottom status writes with transcript/tool output writes so
  spinner refreshes cannot interleave with ordinary output.
- Keep WebSearch, WebFetch, MCP, and local-command status details concise enough
  to fit one terminal row.
- Add regression coverage for wide-character status text, long WebSearch tool
  summaries, and concurrent status refresh during tool output.
- Preserve existing stable UI behavior outside the bottom runtime status row and
  leave the experimental Textual TUI unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: Strengthen the stable runtime status contract so spinner,
  elapsed time, interrupt hint, and active tool detail update atomically and fit
  exactly within the reserved terminal row.

## Impact

- Affected code:
  - `src/deepy/ui/terminal.py`
  - possibly shared width helpers already used by `src/deepy/ui/message_view.py`
  - `tests/test_terminal_ui.py`
  - focused message/status rendering tests if helper behavior is shared
- Affected systems:
  - Stable prompt-toolkit/Rich terminal UI during model turns and local commands
  - WebSearch/WebFetch/MCP tool progress display in stable UI
- No public API, session format, provider behavior, configuration, or
  experimental Textual TUI changes are expected.
