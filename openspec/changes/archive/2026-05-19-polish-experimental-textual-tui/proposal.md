## Why

The experimental Textual TUI has now closed most of the original polish gaps:
normal turns, AskUserQuestion continuation, session/context commands, prompt
history, tool rendering, MCP status, diff navigation, and visual refinements are
usable. The remaining user-visible gap is narrower but important: several
stable terminal UI affordances still either show unsupported messages or have
only a minimal TUI path. This iteration should bring those remaining stable UI
parity items into the opt-in Textual app while preserving the existing stable
`deepy` UI.

## What Changes

- Add an interactive AskUserQuestion continuation surface in the Textual TUI,
  including option selection, multi-select, custom answer, cancellation, and
  same-session continuation.
- Add Textual-native navigation surfaces for command discovery, status/help,
  sessions, skills, model/theme selection, and MCP status where the stable UI
  already exposes equivalent commands.
- Add session and context command support for `/new`, `/sessions`, `/resume`,
  and `/compact` without leaving the TUI.
- Add TUI support for `/init` by reusing the existing AGENTS.md initialization
  model prompt inside the Textual app.
- Add TUI support for `/reset` through a Textual-native configuration reset and
  setup flow rather than embedding prompt-toolkit prompts inside Textual.
- Add TUI support for user-entered `!command` local command mode. The TUI SHALL
  reuse Deepy's existing local command execution and session persistence
  helpers, including the existing Windows non-interactive pipe-based execution
  boundary.
- Connect skill market and full skill management to the TUI, including market
  search/install/update/uninstall/listing and a first-class installed/market
  management surface.
- Replace generic compact tool output for high-value tools with first-class
  Textual blocks for `shell`, `read`, `todo_write`, AskUserQuestion, and MCP
  status/tool results.
- Improve transcript interaction with controlled auto-scroll, input history,
  collapsible detail blocks, and richer keyboard navigation.
- Improve diff usability with wrapping, hunk navigation, hunk folding, and
  narrow/wide terminal coverage while keeping the diff implementation
  Deepy-owned.
- Keep `deepy tui` experimental and opt-in; do not replace the default
  Rich/prompt-toolkit UI in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `experimental-textual-tui`: Mature the opt-in Textual app shell, command
  surfaces, transcript behavior, tool widgets, diff interaction, and test
  coverage.
- `terminal-ui`: Align experimental TUI behavior with Deepy's existing
  user-facing terminal contracts for AskUserQuestion, session commands, model
  and theme selection, help/status, `/init`, `/reset`, local command mode,
  skill management, and readable tool display.
- `session-context`: Expose session resume, new session, and manual compaction
  flows inside the Textual TUI, and persist TUI local-command transcripts using
  the same synthetic shell records as the stable terminal UI.
- `tools`: Define Textual-specific rendering expectations for shell, read,
  todo, web, MCP, and AskUserQuestion tool results while preserving existing
  model-facing tool contracts.

## Impact

- Affected code: `src/deepy/tui/`, `src/deepy/ui/slash_commands.py`,
  `src/deepy/ui/local_command.py`, skill-market helpers, config settings
  helpers, session/compaction helpers under `src/deepy/sessions/`, tool-output
  parsing and rendering helpers under `src/deepy/ui/message_view.py`,
  MCP/status helpers, and Textual headless tests under `tests/`.
- Affected behavior: only the opt-in `deepy tui` path and shared command/tool
  formatting helpers needed by that path.
- Dependencies: no new runtime dependency is required by default. Toad and
  `textual-diff-view` remain reference-only and SHALL NOT be vendored or added
  as dependencies by this change.
- Compatibility: the default `deepy` interactive UI remains unchanged except for
  shared bug fixes or helper extraction that preserve existing behavior.
