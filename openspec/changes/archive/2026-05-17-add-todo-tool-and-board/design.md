## Context

Deepy currently exposes built-in tools through the OpenAI Agents SDK and renders
tool activity in the Rich/prompt-toolkit terminal UI. Complex work can already be
explained through thinking text and final summaries, but there is no structured,
session-scoped task state that the model can update and the user can inspect
throughout a turn.

Reference implementations split this space into multiple features. DeepAgents
and Qwen Code provide a first-class todo tool, Kimi CLI persists a todo list in
session state, and Cline renders a Focus Chain checklist outside the normal chat
flow. This change adopts the first-class todo-tool and board pattern only.
Subagent delegation and plan approval modes remain out of scope.

## Goals / Non-Goals

**Goals:**

- Add a `todo_write` built-in FunctionTool for session-scoped task tracking.
- Keep the tool contract simple: full-list replacement with stable item ids and
  explicit statuses.
- Render todo updates as a compact terminal board, not raw JSON.
- Preserve todo state across resume and compaction.
- Guide the model to use todos for meaningful multi-step work and avoid todo
  churn for simple requests.

**Non-Goals:**

- Do not add subagents or a `task` delegation tool.
- Do not add an EnterPlanMode/ExitPlanMode approval workflow.
- Do not add a `task_progress` argument to every existing tool.
- Do not move todo progress into the interactive status footer.

## Decisions

### Use a standalone `todo_write` tool

Deepy will register a dedicated `todo_write` tool rather than extending every
tool schema with a progress parameter. This matches Qwen Code's model-facing
shape and keeps the current tool contracts stable.

Alternatives considered:

- Cline-style `task_progress` on every tool call: good UI behavior, but invasive
  for Deepy's existing FunctionTool schemas and easy to mix progress updates with
  unrelated tool arguments.
- Kimi-style `SetTodoList`: proven, but the CamelCase name is less consistent
  with Deepy's current lower-case `shell`, `read`, `modify`, and `load_skill`
  tools.
- DeepAgents-style `write_todos`: also valid, but `todo_write` is concise and
  aligns with Qwen Code's explicit tool naming.

### Store normalized todo items as session state

Todo state will be normalized to a list of items:

- `id`: stable string identifier for diffing and rendering
- `content`: user-facing task text
- `status`: `pending`, `in_progress`, or `completed`

The tool will replace the complete list on each write. Empty lists clear the
board. A read mode can be supported by omitting `todos` if implementation finds
it useful for resume/compaction, but the primary model path is full-list writes.

Alternatives considered:

- Store only Markdown checklist text: easy to render, but harder to validate,
  diff, and preserve stable item identity.
- Add `blocked` and `cancelled` statuses in the first version: expressive, but
  less aligned with common reference schemas. The first version can represent
  blockers in task content or final user-facing summaries.

### Render todos as a board separate from footer status

The terminal UI will treat todo state as a dedicated board or compact panel in
the transcript/interactive display layer. The bottom footer remains focused on
model, cwd, MCP, context, newline help, and runtime status lines.

The board should show completion count, current in-progress item, and ordered
items with stable status marks. It should suppress raw tool JSON and avoid
printing a verbose "updated todo list" message on every internal update.

Alternatives considered:

- Footer-only progress: compact, but conflicts with the recently optimized
  footer and hides the actual task list.
- Ordinary tool output only: simple, but repeated JSON-style updates make long
  sessions noisy and hard to scan.

### Preserve todo state in session and compaction context

Todo state must survive `/resume` and manual or automatic compaction. The latest
todo state should be persisted alongside session data or as metadata in session
items, and compaction prompts should preserve active task state so the model can
continue without recreating or forgetting the board.

Alternatives considered:

- Keep todos only in memory: easiest implementation, but loses the board across
  resume and breaks long-running tasks.
- Reconstruct from transcript: brittle and dependent on compaction retaining the
  right tool result text.

## Risks / Trade-offs

- Model overuses `todo_write` for trivial requests -> Mitigate with explicit
  prompt/tool guidance and tests that simple informational prompts do not require
  todo usage.
- Model repeatedly rewrites todos without real progress -> Mitigate with tool
  description guidance, concise tool output, and stable item validation.
- Board rendering becomes noisy in narrow terminals -> Mitigate with compact
  truncation and a focused current-task summary.
- Persisted state and transcript state diverge -> Mitigate by treating the most
  recent validated `todo_write` result as authoritative and updating session
  state atomically with the tool result.
