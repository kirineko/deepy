## 1. Todo Data Model And Runtime

- [x] 1.1 Add a normalized todo item/state model with `id`, `content`, and `status` validation.
- [x] 1.2 Add session-scoped todo state storage to the tool runtime without changing existing file/shell tool behavior.
- [x] 1.3 Implement complete-list replacement semantics, empty-list clearing, and read-without-write behavior if `todos` is omitted.
- [x] 1.4 Reject duplicate ids, empty content, unsupported statuses, and multiple `in_progress` items while preserving the previous valid state.

## 2. Tool Registration And Tool Results

- [x] 2.1 Register `todo_write` in `build_function_tools()` with a strict enough JSON schema for todo items.
- [x] 2.2 Add `ToolRuntime.todo_write()` or equivalent runtime entry point returning `ToolResult` JSON.
- [x] 2.3 Include structured metadata such as `kind="todo_list"`, `todos`, counts, and changed-state indicators in successful results.
- [x] 2.4 Add concise model-facing tool output that discourages repeated calls when no todo state changed.
- [x] 2.5 Add focused tool tests for valid writes, clear, read, validation failures, and FunctionTool registration.

## 3. Session Persistence And Compaction

- [x] 3.1 Persist the latest valid todo state with the active JSONL session or session metadata.
- [x] 3.2 Restore persisted todo state on `/resume` and make it available to the UI before the next turn.
- [x] 3.3 Preserve todo state through manual and automatic compaction rewrites.
- [x] 3.4 Include active todo context in compaction prompts so the model can continue or reconcile the plan.
- [x] 3.5 Add session and compaction tests for todo persistence, restore, invalid-update preservation, and compacted-session continuity.

## 4. Terminal Todo Board

- [x] 4.1 Extend tool-output parsing to recognize todo-list metadata without parsing raw prose.
- [x] 4.2 Add a todo board renderer with progress count, current task, and distinct pending/in-progress/completed markers.
- [x] 4.3 Render todo updates in live output and session history without exposing raw todo JSON as the primary display.
- [x] 4.4 Keep todo board rendering separate from the bottom footer and runtime status line.
- [x] 4.5 Handle narrow terminal widths with truncation or compact summaries that preserve the current task and progress count.
- [x] 4.6 Add UI/message-view tests for board rendering, theme-compatible styles, history rendering, and footer separation.

## 5. Agent Instructions And Tool Docs

- [x] 5.1 Add `todo_write` tool documentation describing when to use it and when to skip it.
- [x] 5.2 Update system prompt/tool guidance for complex requests, one active item, real-progress updates, and final reconciliation.
- [x] 5.3 Ensure guidance explicitly excludes subagent/task delegation and plan approval mode from this change.
- [x] 5.4 Add prompt-generation tests that verify todo guidance is present and simple-request anti-churn guidance is included.

## 6. Verification

- [x] 6.1 Run focused tests for tools, message view, terminal UI, prompts, sessions, and compaction.
- [x] 6.2 Run the broader test suite after focused tests pass.
- [x] 6.3 Manually inspect representative dark and light terminal render strings for the todo board and unchanged footer styling.
- [x] 6.4 Validate the OpenSpec change with `openspec validate add-todo-tool-and-board --strict`.
