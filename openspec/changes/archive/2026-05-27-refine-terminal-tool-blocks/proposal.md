## Why

Stable terminal output currently uses content-width Rich panels for Shell and
todo details, which makes repeated command output feel heavy and visually
uneven. The startup welcome panel also reads taller than necessary for a
first-screen summary compared with compact long-strip agent welcome layouts.

## What Changes

- Render Shell command output as a lightweight full-width output block associated
  with the preceding `[Shell]` status line, without repeating a panel title.
- Render todo updates as a compact full-width progress block with stable
  alignment and no duplicated footer/status information.
- Refresh the stable terminal welcome panel into a wider, lower long-strip
  layout that preserves the required identity, model, provider, theme, cwd, and
  core-command information.
- Keep existing tool result summaries, diff previews, Markdown rendering, and
  experimental Textual TUI behavior unchanged.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Refine stable terminal Shell/Todo output blocks and welcome
  layout behavior.

## Impact

- Affected code: `src/deepy/ui/message_view.py`,
  `src/deepy/ui/terminal.py`, `src/deepy/ui/welcome.py`.
- Affected tests: focused stable terminal rendering tests in
  `tests/test_message_view.py`, `tests/test_terminal_ui.py`, and
  `tests/test_welcome.py`.
- No tool schema, provider, session storage, or MCP behavior changes.
