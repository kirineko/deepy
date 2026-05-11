## bash

Use `bash` for repository inspection, tests, builds, and shell commands that are appropriate for the current project.

Parameters:

- `command`: The shell command to run.
- `timeout_ms`: Optional timeout in milliseconds.

Behavior:

- Runs in the session working directory.
- Preserves the last working directory for subsequent shell calls.
- Returns stdout and stderr in the standard tool result JSON.
