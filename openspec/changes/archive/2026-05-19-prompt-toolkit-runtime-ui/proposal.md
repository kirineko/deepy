## Why

Deepy's current interactive terminal split ownership between prompt-toolkit
idle input, Rich transcript output, and a hand-written ANSI runtime status
overlay. Terminal testing showed that patching bottom-row ANSI ownership
produces fragile regressions. This change keeps the stable portion: move idle
input/footer ownership behind a prompt-toolkit boundary, cap multiline input
height, remove the unstable ANSI runtime footer path, and leave full running
interaction to a follow-up TUI proposal.

## What Changes

- Introduce a prompt-toolkit-owned input/footer boundary for interactive idle
  prompts.
- Preserve a runtime delegate model as preparation for a future global TUI,
  without keeping the experimental `prompt_async` running-turn lifecycle in
  this change.
- Keep completed transcript output in Rich after prompt-toolkit ownership ends.
- Remove `_TerminalBottomStatus` and the competing ANSI scroll-region footer
  path.
- Add PTY-focused regression coverage for prompt-at-bottom behavior, model
  turns, local command output, and post-run transcript stability.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Change interactive input/footer ownership so prompt-toolkit
  owns idle prompt layout, while Rich owns completed transcript output. Running
  status display is deferred to the follow-up global TUI change.

## Impact

- Affected code:
  - `src/deepy/ui/prompt_input.py`
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/status_footer.py`
  - related terminal rendering helpers and tests
- Affected tests:
  - `tests/test_prompt_input.py`
  - `tests/test_terminal_ui.py`
  - new or expanded PTY integration tests for interactive rendering
- No public CLI command syntax changes are expected.
- No new runtime dependency is expected; this should build on prompt-toolkit
  and Rich already in use.
