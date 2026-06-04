## 1. Keep Single Runtime Overlay

- [x] 1.1 Use `_status_display(...)` for model turns with a single terminal-bottom runtime status row.
- [x] 1.2 Use `_status_display(...)` for local command execution with a single terminal-bottom runtime status row.
- [x] 1.3 Remove the second fixed prompt-footer row from runtime status rendering.
- [x] 1.4 Ensure runtime paths reserve no more than one fixed terminal-bottom row.

## 2. Preserve Existing Footer Behavior

- [x] 2.1 Keep `StatusFooter` and structured prompt toolbar rendering intact.
- [x] 2.2 Keep `PROMPT_TOOLBAR_HELP` as `newline: ctrl+j`.
- [x] 2.3 Keep concise footer labels such as `model <name>[mode]`, `[AGENTS.md]`, `mcp N`, and `ctx ...`.
- [x] 2.4 Keep thinking transcript text realtime and out of runtime status/footer content.
- [x] 2.5 Keep submitted user prompts as a single green transcript copy, including multiline prompts.
- [x] 2.6 Keep multiline submitted prompts visible above the runtime status row when active work starts.

## 3. Test Updates

- [x] 3.1 Remove tests that assert a second reserved prompt-footer row during active work.
- [x] 3.2 Add/update tests proving runtime status reserves only one bottom row and does not write overlay output to recorded consoles.
- [x] 3.3 Keep existing tests for prompt footer content, structured status segments, and immediate thinking transcript output.
- [x] 3.4 Update local command runtime status tests to match one-line runtime status behavior.
- [x] 3.5 Add tests for clearing prompt_toolkit's submitted prompt echo before printing the green transcript copy.
- [x] 3.6 Add tests for one-line runtime-status anchoring after multiline prompt submission.

## 4. Verification

- [x] 4.1 Run focused terminal UI and prompt tests.
- [x] 4.2 Run formatting/lint/type checks required by the repo for this change scope.
- [x] 4.3 Run OpenSpec validation for the change.
