## Why

Deepy's interactive status footer has accumulated useful but noisy details, including duplicated model/reasoning fields, permanent exit-help text, and mixed casing across status segments. The footer should stay visible through normal interaction while using a compact, consistent format that is easy to scan.

## What Changes

- Keep the interactive status footer visible across idle prompt input, model work, and local command work.
- Merge model and reasoning mode into one compact segment, for example `model deepseek-v4-pro[max]`.
- Remove permanent `Ctrl+D twice exit` help from the footer while preserving the existing two-step Ctrl+D exit behavior and confirmation prompt.
- Shorten context status from `ctx win ...` to a compact `ctx ...` or `context ...` segment while preserving current context-window accounting semantics.
- Shorten MCP status to `mcp N`.
- Shorten AGENTS.md status to a bracketed loaded indicator, `[AGENTS.md]`, while preserving the file name's exact case.
- Normalize footer segment casing so non-file-label status keys use a consistent lowercase style.
- Improve the footer's visual treatment so stable status, active work, loaded indicators, separators, and muted metadata have clear hierarchy in both light and dark themes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Update the interactive status footer requirements for persistence, compact status labels, model/reasoning display, MCP indicator display, visual hierarchy, and footer help removal.
- `agent-instructions`: Update the AGENTS.md footer indicator from verbose loaded text to a compact bracketed indicator while preserving the exact case-sensitive filename.

## Impact

- Affected code:
  - `src/deepy/ui/prompt_input.py`
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/styles.py`
  - terminal UI tests covering prompt toolbar, context footer, interactive loop toolbars, and working-status display
- Affected specs:
  - `openspec/specs/terminal-ui/spec.md`
  - `openspec/specs/agent-instructions/spec.md`
- No CLI command, config file, model protocol, session format, or dependency changes are expected.
