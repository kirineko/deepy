## Why

Windows validation found that local command mode can corrupt the interactive
prompt after running `!` commands through `pywinpty`. The failure shows raw
terminal control sequences in subsequent input and misaligned shell output
panels, which makes the feature unreliable on Windows even though it works on
macOS and Linux.

This change prioritizes a stable Windows user experience over full TTY
simulation. Local command mode should remain useful for known, non-interactive
commands without taking over or mutating the parent terminal state.

## What Changes

- Replace Windows `pywinpty` local command execution with a simpler
  non-interactive subprocess runner.
- Remove the Windows `pywinpty` package dependency from the project.
- Treat Windows local command mode as intentionally non-interactive:
  stdin is closed or redirected, stdout/stderr are captured, and interactive TUI
  programs are not supported.
- Normalize Windows command output before rendering and context persistence:
  CRLF/CR line endings become LF, and terminal control sequences are removed.
- Preserve existing synthetic shell transcript behavior so `!cmd` input and
  command results still enter session context for later model turns.
- Keep POSIX local command behavior unchanged except where shared output
  normalization helpers are reused.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Windows local command mode becomes a stable non-interactive
  terminal UI path that must not corrupt subsequent prompt input or render raw
  control sequences.
- `session-context`: Local command transcripts must continue to be persisted as
  synthetic shell tool items after the Windows execution strategy changes.
- `runtime-environment`: Runtime behavior must document that Windows local
  command mode does not allocate a pseudo-terminal and does not support
  interactive TTY commands.

## Impact

- `pyproject.toml` and `uv.lock`: remove `pywinpty`.
- `src/deepy/ui/local_command.py`: replace Windows runner, output
  normalization, timeout handling, and metadata.
- `src/deepy/ui/message_view.py` or shared rendering helpers: ensure shell
  output blocks render sanitized text.
- `tests/test_local_command.py`, `tests/test_terminal_ui.py`, and related
  tests: cover Windows subprocess execution, control-sequence sanitization,
  timeout behavior, and session persistence.
