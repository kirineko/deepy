## 1. Status Line Width Fitting

- [x] 1.1 Replace character-count truncation/padding for bottom runtime status text with display-cell-aware fitting.
- [x] 1.2 Ensure fitted lines occupy exactly the reserved terminal row width in display cells.
- [x] 1.3 Preserve spinner, elapsed time, and Esc interrupt hint when long tool details require truncation.
- [x] 1.4 Add unit tests for CJK WebSearch details, long ASCII details, very narrow terminal widths, and shorter refreshes after longer lines.

## 2. Terminal Write Coordination

- [x] 2.1 Introduce a stable terminal output lock or writer abstraction shared by bottom status updates and transcript/tool output writes.
- [x] 2.2 Guard `_TerminalBottomStatus.start()`, `update()`, and `clear()` without widening lock scope around model callbacks.
- [x] 2.3 Guard stream event printing paths that can run while the background status refresh thread is active.
- [x] 2.4 Add tests proving status refresh and tool output writes do not interleave in representative fake TTY output.

## 3. Runtime Status Detail Hygiene

- [x] 3.1 Keep tool-call status detail concise for WebSearch, WebFetch, MCP, shell, and thinking states.
- [x] 3.2 Ensure tool output JSON, large result bodies, diffs, and shell output never enter the realtime status detail.
- [x] 3.3 Preserve existing stable labels such as `thinking`, `local command`, and `tool <summary>`.

## 4. Regression Boundaries

- [x] 4.1 Verify Windows and POSIX submitted-prompt bottom-anchor tests still pass after writer changes.
- [x] 4.2 Verify stable local command runtime status still clears cleanly after success, failure, timeout, and interruption.
- [x] 4.3 Verify experimental Textual TUI code paths are not changed by this fix.

## 5. Validation

- [x] 5.1 Run focused stable terminal UI tests in `tests/test_terminal_ui.py`.
- [x] 5.2 Run focused message rendering tests if shared display-cell helpers are changed.
- [x] 5.3 Run formatting/lint checks required by the touched files.
- [x] 5.4 Validate the OpenSpec change with `openspec validate stabilize-stable-runtime-status-line --type change --strict`.
