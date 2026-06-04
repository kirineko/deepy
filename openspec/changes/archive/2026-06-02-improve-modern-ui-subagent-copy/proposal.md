## Why

Modern UI currently keeps subagent tool output too compact: a completed subagent
block can show only `Subagent <name> ok`, leaving the user with no visible report
unless the main assistant repeats it. This makes delegated work feel stalled or
opaque even though the subagent completed successfully.

Modern UI copy behavior also needs a smaller, explicit keyboard path. The prior
contract relied on terminal-native selection and prohibited app-level copy
bindings, but users on macOS expect `Cmd+C`, and `Ctrl+C` is already no longer
advertised as the interrupt shortcut.

## What Changes

- Add a Modern UI-only expandable subagent transcript block behavior:
  - collapsed subagent blocks stay compact and show the assigned parameters;
  - expanded subagent blocks reveal the assigned task and final report;
  - only subagent tool blocks receive this expandable report surface.
- Keep other regular tool output hidden unless it already has a dedicated visible
  surface such as local command output or todo output.
- Add Modern UI copy bindings for `Ctrl+C` and `Cmd+C`/`super+c` that copy the
  currently focused transcript block through Textual's clipboard API.
- Keep Kitty keyboard protocol disabled by default and continue honoring an
  explicit user environment override.
- Do not change shell concurrency behavior in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `experimental-textual-tui`: Modern UI transcript copy behavior and subagent
  block rendering requirements change.
- `subagents`: Subagent lifecycle visibility gains a focused expanded-report
  presentation requirement for rich transcript UIs.

## Impact

- Affected code:
  - `src/deepy/tui/app.py`
  - `src/deepy/tui/widgets.py`
  - `tests/test_tui_app.py`
- Affected specs:
  - `openspec/specs/experimental-textual-tui/spec.md`
  - `openspec/specs/subagents/spec.md`
- No dependency changes are expected.
- No CLI, provider, shell tool, or Classic UI behavior changes are intended.
