## Why

Deepy users sometimes know exactly which local command they want to run and do
not need a model turn to mediate it. A `!` command mode lets the interactive
prompt act like a terminal shortcut while still preserving the command and
result as context for later model turns.

## What Changes

- Add an interactive local command mode for prompts whose trimmed text starts
  with `!`.
- Execute the text after `!` directly in the user's detected runtime shell
  instead of sending that prompt to the model.
- Prefer PTY/TTY execution so terminal-aware commands behave like they are
  running in a real terminal.
- Support Windows TTY execution by allowing a `pywinpty` runtime dependency.
- Render the command result in the terminal, including output and exit status.
- Persist the command and its result into the active session as a synthetic
  shell tool transcript so subsequent model turns can reason from it.
- Keep terminal display output allowed to be longer than the output persisted
  into context; truncate the stored transcript independently.
- Treat non-interactive commands as the first supported target; full-screen or
  long-lived interactive programs are out of scope for the first version.
- Do not support `cd` or other command-mode working-directory mutation. Each
  local command runs from Deepy's active project root.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Interactive prompt behavior gains `!` local command mode and
  terminal rendering for local command results.
- `session-context`: Sessions persist local command-mode input and output as
  replayable context for future model turns.

## Impact

- Interactive terminal input routing in `src/deepy/ui/terminal.py`.
- New local command runner code for PTY/TTY execution, shell selection, output
  capture, timeout/interruption, exit status, and metadata.
- Optional Windows TTY dependency configuration for `pywinpty`.
- Session JSONL writing for synthetic shell tool call/result transcripts.
- Context token accounting and footer updates after local command turns.
- Terminal rendering tests, session replay tests, and platform-specific command
  runner tests.
