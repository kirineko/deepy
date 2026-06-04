## 1. Cursor Position Detection

- [x] 1.1 Refactor stable UI cursor-row probing so `_submitted_prompt_needs_status_anchor()` can use platform-specific providers while preserving its current policy shape.
- [x] 1.2 Keep the existing POSIX `/dev/tty` ANSI cursor report implementation as the non-Windows provider.
- [x] 1.3 Add a Windows provider using standard-library Win32 console APIs to return the cursor row relative to the visible console window.
- [x] 1.4 Make cursor probing fail closed without raising if the terminal handle, console buffer info, or platform support is unavailable.

## 2. Bottom-Anchor Behavior

- [x] 2.1 Wire the Windows provider into submitted prompt anchor detection for stable terminal UI model turns.
- [x] 2.2 Wire the same anchor detection into stable terminal UI local command submissions.
- [x] 2.3 Add a narrow Windows fallback for unreadable cursor position if needed, keeping POSIX behavior unchanged.
- [x] 2.4 Ensure `_TerminalBottomStatus.start()` still creates scrollable space only when anchor output is requested.

## 3. Regression Tests

- [x] 3.1 Add unit tests for Windows console buffer cursor-row conversion, including scrolled buffer windows.
- [x] 3.2 Add tests proving Windows bottom-row prompt submission requests anchor scroll space.
- [x] 3.3 Add tests proving Windows non-bottom prompt submission does not add anchor scroll space solely because it is Windows.
- [x] 3.4 Add tests proving unreadable Windows cursor state does not crash the turn and follows the documented fallback.
- [x] 3.5 Keep existing POSIX cursor report and submitted prompt echo tests passing.

## 4. Validation

- [x] 4.1 Run focused stable UI tests for `tests/test_terminal_ui.py`.
- [x] 4.2 Run formatting/lint checks required by the touched files.
- [x] 4.3 Validate the OpenSpec change with `openspec validate fix-windows-stable-ui-bottom-anchor --type change --strict`.
- [x] 4.4 Manually verify in Windows Terminal / PowerShell that a submitted prompt at the bottom scrolls up above the runtime status row.
- [x] 4.5 Manually verify on macOS that the existing stable UI bottom-anchor behavior is unchanged.
