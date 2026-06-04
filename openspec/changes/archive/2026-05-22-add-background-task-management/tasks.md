## 1. Background Task Core

- [x] 1.1 Add a Deepy-owned background task manager module with task id generation, task records, status transitions, lookup, list, and bounded terminal-task retention.
- [x] 1.2 Implement background process launch with stdout/stderr capture to task-specific log files and prompt return after successful registration.
- [x] 1.3 Implement task output reading with bounded tail/preview, output size metadata, and "more output available" signaling.
- [x] 1.4 Implement stop and stop-all behavior with graceful termination, force kill after a bounded grace period, and idempotent handling of terminal tasks.
- [x] 1.5 Add unit tests for lifecycle transitions, output capture, output preview, stop idempotence, capacity rejection, and retention behavior.

## 2. Tool Integration

- [x] 2.1 Extend the shell tool schema and docs with `run_in_background` while preserving foreground behavior by default.
- [x] 2.2 Wire background shell launches through the background task manager and return structured task metadata immediately.
- [x] 2.3 Add `task_list`, `task_output`, and `task_stop` tools with model-facing descriptions and structured error handling.
- [x] 2.4 Update tool output summaries/rendering so background task launch and management results are concise and readable.
- [x] 2.5 Add tool tests for foreground compatibility, background launch, task listing, output read with and without blocking, stop, unknown task id, and launch failure.

## 3. Stable Terminal UI

- [x] 3.1 Thread a shared background task manager through the stable interactive UI and foreground run/tool runtime boundaries.
- [x] 3.2 Add `/ps` slash command handling, help text, and completion/suggestion entries.
- [x] 3.3 Add `/stop` slash command handling, help text, and completion/suggestion entries.
- [x] 3.4 Keep background task output out of `TerminalStreamRenderer`, active thinking, assistant response, and foreground tool transcript rendering.
- [x] 3.5 Add optional concise background task count/status to the idle prompt/status context without printing unsolicited output.
- [x] 3.6 Add terminal UI tests for `/ps`, `/stop`, no-task messages, help output, session preservation, and output non-interference.

## 4. Exit Cleanup And Textual Compatibility

- [x] 4.1 Wire stop-all cleanup into `/exit`, `/quit`, Ctrl+D-confirmed exit, and KeyboardInterrupt paths before MCP runtime cleanup.
- [x] 4.2 Wire equivalent bounded cleanup into the experimental Textual TUI exit path.
- [x] 4.3 Ensure unsupported `/ps` or `/stop` handling in Textual TUI is explicit if native handling is not implemented in this change.
- [x] 4.4 Add tests covering exit cleanup order and running background task termination for stable UI and Textual TUI paths.

## 5. Documentation And Validation

- [x] 5.1 Update user-facing docs for background shell usage, `/ps`, `/stop`, task output inspection, and exit cleanup behavior.
- [x] 5.2 Update model/tool guidance so background mode is recommended only for long-running commands, servers, watchers, and tasks that should be inspected later.
- [x] 5.3 Run targeted tests for background task manager, tools, stable terminal UI, and Textual cleanup compatibility.
- [x] 5.4 Run `openspec validate add-background-task-management --strict`.
