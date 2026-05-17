## todo_write

Maintain a session-scoped todo list for complex work.

Use `todo_write` when the user asks for several deliverables, the work touches
multiple files, or the task naturally breaks into three or more meaningful
steps. Do not use it for simple questions, tiny one-step edits, or routine
commands where a todo list would add noise.

Each update replaces the complete list. Keep item `id` values stable across
updates. Use exactly one `in_progress` item at a time, mark completed work as
`completed`, and update the list only when real progress changes. Omit `todos`
to read the current list; pass an empty list to clear it.

This tool only tracks progress. It does not delegate to subagents and it does
not request plan approval.
