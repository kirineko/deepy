## Why

Deepy currently maintains a stable Rich/prompt-toolkit UI and an experimental
Textual TUI with overlapping behavior, which increases maintenance cost and
forces every user-visible UI improvement through two surfaces. The stable UI is
mature today, but its prompt-toolkit/Rich shell is a poor fit for future
app-like UX such as overlays, navigable transcript blocks, richer pickers,
queue/steer interactions, and compact persistent panels.

This change makes the Textual UI the future primary terminal UI candidate by
first rebuilding it around Textual-native layout, input, and composition
patterns. It does not immediately delete the stable UI; it creates the quality
and behavioral foundation required before that future removal can be safe.

## What Changes

- Redesign the Textual TUI visual structure into a compact terminal-agent shell:
  transcript scrollback, lightweight status line, bottom composer, overlay
  suggestions, and modal/picker surfaces instead of heavy header/footer/sidebar
  chrome.
- Rebuild the Textual composer so the prompt text contains only user-authored
  text. Attachments, generated suggestions, slash/file suggestions, and prompt
  state are rendered as Textual-native adjacent surfaces instead of being
  encoded as visible replacement text inside the input buffer.
- Prefer native Textual input features, including compact `TextArea`, native
  suggestion support, soft wrapping, cursor APIs, and Textual test hooks. Any
  terminal-protocol normalization must be invisible defensive handling at the
  input boundary, not a visible character-replacement UX.
- Preserve stable UI behavior expectations in the redesigned Textual surface:
  Enter submits, Ctrl+J inserts a newline, slash commands, `@file` mentions,
  input suggestions, image attachment submission, audit approvals,
  AskUserQuestion continuation, status, skills, model selection, background
  task cleanup, session resume, and exit summary.
- Introduce a shared command registry shape inspired by Hermes so help,
  suggestions, Textual command surfaces, and future stable-UI retirement do not
  rely on parallel command definitions.
- Add UX hooks that prepare for useful Hermes-style capabilities such as
  categorized help, command aliases, queue/steer busy behavior, external editor
  prompt editing, collapsible tool detail modes, and session/picker overlays.
- Keep `deepy tui` as the experimental entrypoint during this change while
  making it clear in specs and docs that the redesigned Textual UI is the
  candidate for the future default interactive UI.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `experimental-textual-tui`: redefine the experimental TUI contract around a
  Textual-first compact shell, native composer behavior, and future-primary UI
  readiness.
- `terminal-ui`: align stable UI behavioral expectations with the redesigned
  Textual surface so parity is defined by user experience and command semantics,
  not by keeping two independent implementations forever.
- `product`: clarify that Textual remains opt-in for this change but is being
  prepared as the future primary terminal UI.
- `user-documentation`: update UI/TUI documentation requirements so docs cover
  the redesigned Textual-first direction, current entrypoints, and the future
  stable-UI retirement goal without promising an immediate default switch.

## Impact

- Affected code areas include `src/deepy/tui/app.py`,
  `src/deepy/tui/widgets.py`, `src/deepy/tui/screens.py`,
  `src/deepy/tui/commands.py`, `src/deepy/tui/state.py`,
  `src/deepy/ui/slash_commands.py`, shared prompt/file mention/image
  attachment helpers, status/footer helpers, and tests under
  `tests/test_tui_app.py`, `tests/test_tui_diff.py`, and focused shared UI
  tests.
- The stable Rich/prompt-toolkit UI remains available during this change, but
  new Textual UI work should avoid adding new stable/TUI duplicate behavior
  unless needed for safety or compatibility.
- No new non-Python runtime is introduced. Hermes' React/Ink TUI architecture is
  treated as a design reference, not as a dependency or implementation target.
- Documentation and OpenSpec contracts must reflect the staged migration: first
  rebuild Textual TUI quality, then evaluate default-entrypoint migration, then
  retire the stable UI in a later change.
