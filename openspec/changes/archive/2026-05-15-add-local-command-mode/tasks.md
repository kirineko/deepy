## 1. Dependency And Test Setup

- [x] 1.1 Add `pywinpty` as a Windows-only runtime dependency.
- [x] 1.2 Add parser tests for local command mode detection, including `!cmd`, whitespace before `!`, empty `!`, and normal prompts.
- [x] 1.3 Add command-runner tests for successful command output, non-zero exit, timeout/interruption metadata, and display truncation.
- [x] 1.4 Add session tests proving synthetic shell transcript items replay through `DeepyJsonlSession.get_items()`.
- [x] 1.5 Add terminal integration tests proving `!` bypasses `run_once` and normal prompts still call `run_once`.

## 2. Local Command Runner

- [x] 2.1 Create a local command runner module with a result object containing command, output, exit code, cwd, shell metadata, TTY mode, duration, timeout, and truncation fields.
- [x] 2.2 Implement POSIX PTY execution with the detected zsh/bash shell and bounded output capture.
- [x] 2.3 Implement Windows PTY execution using `pywinpty`, including a clear error when the dependency is unavailable.
- [x] 2.4 Execute every local command from the active project root and do not persist cwd changes from commands such as `cd`.
- [x] 2.5 Add timeout/interruption handling that terminates the child process when possible and returns partial output.
- [x] 2.6 Apply separate limits for terminal-display output and context-stored output.

## 3. Synthetic Transcript Persistence

- [x] 3.1 Build helper functions that convert a local command result into synthetic user, assistant shell tool call, and shell tool result SDK items.
- [x] 3.2 Include command-mode metadata in the shell tool result JSON, including TTY mode and context-output truncation state.
- [x] 3.3 Append synthetic transcript items to the active `DeepyJsonlSession` after command completion.
- [x] 3.4 Ensure local command transcript appends update session index context estimates without recording model token usage.
- [x] 3.5 Verify session history rendering uses the existing shell output display path for synthetic command results.

## 4. Interactive Terminal Integration

- [x] 4.1 Add local command mode detection to `run_interactive` before model execution.
- [x] 4.2 Handle empty `!` input with a concise usage message and no session append.
- [x] 4.3 Render local command output and exit/interruption status in the interactive terminal.
- [x] 4.4 Update the footer/context status after local command transcript persistence.
- [x] 4.5 Preserve existing slash command, normal prompt, Ctrl+D, Ctrl+J, and file mention behavior.

## 5. Documentation And Verification

- [x] 5.1 Update user-facing help or README documentation for `!` command mode and its non-interactive-command-first scope.
- [x] 5.2 Run focused tests for local command runner, session persistence, and terminal UI.
- [x] 5.3 Run the full `uv run pytest` suite.
- [x] 5.4 Run `uv run ruff check`.
- [x] 5.5 Run `uv run pyright`.
- [x] 5.6 Run OpenSpec validation for `add-local-command-mode`.
