## Why

Complex coding requests are hard to follow when progress only appears as
thinking text, tool logs, and final summaries. Deepy needs a first-class todo
tool and terminal board so the model can plan, track, and expose task progress
without mixing progress state into ordinary chat output or the status footer.

## What Changes

- Add a model-facing `todo_write` tool for maintaining a session-scoped task
  list.
- Add a terminal todo board that renders the latest task list and progress in a
  compact, readable form.
- Persist todo state with the active session so resume and compaction can
  preserve the current task plan.
- Add model guidance for when to use and update todos, and when to skip them for
  simple requests.
- Do not add subagents, a `task` delegation tool, or a plan approval mode in
  this change.

## Capabilities

### New Capabilities

- `todo-planning`: Session-scoped todo tracking and terminal progress board for
  complex user requests.

### Modified Capabilities

- `tools`: Register and execute the `todo_write` tool through the existing
  OpenAI Agents SDK tool flow.
- `terminal-ui`: Render todo updates as a task board instead of raw tool JSON or
  footer-only text.
- `session-context`: Persist and restore the latest todo state across session
  resume and context compaction.
- `agent-instructions`: Instruct the model to use todos for meaningful
  multi-step work while avoiding todo churn for simple requests.

## Impact

- Affected code likely includes tool registration/runtime, tool result metadata,
  terminal message rendering, session JSONL/state handling, compaction context,
  and agent instruction generation.
- No external service dependency is expected.
- The existing footer/status-bar behavior should remain separate from todo board
  rendering.
