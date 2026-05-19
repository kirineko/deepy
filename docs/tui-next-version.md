# Deepy TUI Next Version Handoff

Date: 2026-05-19

This document tracks the current state of the experimental `deepy tui` after the
`polish-experimental-textual-tui` apply pass. It replaces the earlier pre-apply
checklist: most of the original parity gaps have now been implemented, while a
small set of intentional next-version gaps, structural follow-ups, and Windows
verification tasks remain open.

## Current Status

`deepy tui` remains an opt-in experimental Textual app. It does not replace the
stable Rich and prompt-toolkit UI started by `deepy`.

The TUI now supports normal model turns, live thinking and tool rendering,
session continuity, first-class command surfaces, AskUserQuestion continuation,
session/context commands, richer tool-specific blocks, prompt history,
controlled auto-scroll, interactive diff navigation, file mention completion,
slash command completion, and core visual polish. The code path still uses the
shared Deepy runner and shared model-facing tool contracts.

OpenSpec progress for `polish-experimental-textual-tui` is currently `49/54`.
The remaining items are either intentional next-version feature gaps,
follow-up refactors, or Windows cross-platform verification.

Manual macOS validation for the current pass has been completed. Based on that
validation and the current implementation, the TUI is broadly aligned with the
stable `deepy` UI for core chat, session, context, AskUserQuestion, tool
rendering, prompt history, slash/file completion, resume, compact, MCP status,
model/theme, scrolling, and diff workflows. The gaps below should be treated as
known next-version work rather than regressions in this pass.

## Implemented

### Entry And Compatibility

- `deepy tui` still starts the experimental Textual app.
- The default `deepy` command still starts the stable Rich/prompt-toolkit UI.
- The TUI remains under `src/deepy/tui/`, parallel to `src/deepy/ui/`.
- Toad and `textual-diff-view` remain reference-only; they are not imported,
  vendored, or added as dependencies.
- The TUI consumes shared runner events and shared `ToolResult` JSON payloads
  rather than defining separate model/tool contracts.

### Structure And State

- Added a small `TuiController` boundary for per-TUI state such as loaded
  skills, prompt history, prompt draft restoration, and session reset.
- Added dedicated TUI modules for command catalog/provider support and reusable
  modal screens.
- Preserved external CLI entrypoints and stable terminal UI behavior.

Still open:

- Further split the large app/widget modules into focused transcript, tool
  widget, command, and prompt-history modules. The functional boundary exists,
  but the code is not yet fully extracted.

### Command Discovery And Slash Commands

- Added a Textual command provider for TUI commands grouped by help, session,
  skills, settings, tools, and system commands.
- Slash suggestions continue to work from the prompt.
- Unknown slash commands no longer start accidental model turns.
- Unsupported stable commands now show explicit TUI unsupported messages.
- `/help` opens a Textual help surface with commands, keybindings, model,
  session, loaded skills, config path, and core state.
- `/status` opens a dismissible status surface with project, model, reasoning,
  session, context, MCP, loaded skills, and theme information.
- `/theme` persists `auto`, `dark`, and `light` through existing settings.
- `/model` supports direct model/reasoning changes and picker-based selection.
- `/mcp` shows MCP status without leaving the TUI.
- `/exit` and `/quit` exit without starting a model turn.

Implemented session/context commands:

- `/new`
- `/sessions`
- `/resume [ID]`
- `/compact [focus]`

Still intentionally unsupported in TUI after this pass:

- `/init` shows an explicit unsupported message. Use the stable `deepy` UI for
  AGENTS.md initialization for now.
- `/reset` shows an explicit unsupported message. Use the stable `deepy` UI for
  config reset/setup for now.

Additional command parity gaps deferred to the next version:

- `!command` local shell command mode is not implemented in the TUI. The TUI
  renders model-invoked `shell` tool output, but it does not actively execute
  user-entered local commands.
- Skill market and full skill management are not connected in the TUI. The TUI
  supports local skill listing/loading/showing and `/skill:NAME` invocation,
  but market search/install/update/uninstall and the full skill management menu
  remain stable-UI-only.

### AskUserQuestion Continuation

- Pending `RunSummary.pending_questions` are normalized and rendered inside the
  TUI.
- Single-select answers submit and continue the same session id.
- Multi-select answers submit and continue the same session id.
- Custom answers are supported when the question offers an "other" path.
- Cancellation is recoverable and records clear transcript feedback.
- Answer submissions reuse the stable AskUserQuestion formatting path.

### Session And Context Flow

- `/new` clears the active session id and resets per-session TUI state without
  changing global settings.
- `/sessions` opens a navigable Textual session picker using existing JSONL
  session entries.
- `/resume [ID]` supports direct resume.
- Picker-based resume is supported.
- Visible transcript history is restored from previous session items.
- `/compact [focus]` uses the existing durable compaction flow.
- Compaction running, success, no-op, and failure states are rendered inside the
  TUI.

### Tool-Specific Surfaces

- Added reusable expandable tool blocks with summary, status, metadata, hidden
  details, keyboard expansion, and pointer expansion.
- Model-invoked `shell` output now shows command, cwd, exit code, status,
  duration, stdout, stderr, truncation, timeout, and interruption metadata when
  present.
- `read` output has a file preview treatment with path/range metadata and
  folded large content.
- `todo_write` renders a main-transcript todo board with progress, current item,
  task markers, and a side-panel projection for quick reference.
- `WebSearch` and `WebFetch` show source/URL metadata with expandable bodies.
- MCP tool/status results show server/tool identity, success/failure/cleanup or
  unavailable state, and concise errors.
- Stdio MCP child-process stderr is suppressed in TUI runs so server startup
  banners do not overwrite prompt input.
- Tool waiting-for-user state has dedicated visual treatment.
- `load_skill` continues to summarize skill metadata without dumping full
  `SKILL.md` bodies.
- Model-facing tool names, argument schemas, and JSON result contracts are
  preserved.

### Transcript, Diff, And Visual Polish

- Controlled auto-scroll distinguishes bottom-anchored output from the user
  reading older transcript history.
- A "new output below" status affordance appears when output arrives while the
  user is away from the bottom.
- Prompt input history supports Ctrl+Up and Ctrl+Down without losing the
  current draft.
- Thinking and tool labels use consistent title treatment and semantic state
  colors.
- Diff views track hunk boundaries.
- Diff blocks support next/previous hunk navigation.
- Diff blocks support hunk fold/unfold.
- Long changed diff lines are constrained to terminal width with ellipsis
  folding.
- Large diffs remain truncated in the TUI diff model.

Still open:

- Optional wide-layout or side-by-side diff behavior. The current single-column
  fallback is the supported behavior.
- Manual narrow and wide layout verification for overlap, prompt stability, and
  side-panel behavior.

## Tests And Validation

Added or updated coverage includes:

- Textual command provider discovery and search.
- Slash command dispatch and unsupported command messages.
- `/help`, `/status`, `/theme`, and `/model` surfaces.
- AskUserQuestion single-select, multi-select, selected-option markers,
  non-duplicated tool chrome, custom answer Enter submission, cancellation, and
  same-session continuation.
- `/new`, `/sessions`, `/resume`, transcript restoration, and `/compact`.
- Tool widget behavior for shell, read, todo progress, web, MCP,
  waiting-for-user, expansion, and truncation.
- MCP stdio stderr suppression to keep server banners out of the prompt area.
- Diff wrapping, hunk tracking, hunk navigation, hunk folding, truncation,
  narrow width, and wide width.
- Controlled auto-scroll, new-output indicator, prompt-submit scroll recovery,
  and input-history regressions.
- Continued regression coverage for stream ordering, duplicate final messages,
  skill loading, usage lines, errors, and AGPL reference package avoidance.

Latest verification:

- `uv run pytest tests/test_tui_app.py tests/test_tui_diff.py -q`: `46 passed`
- `uv run pytest -q`: `668 passed`
- `uv run ruff check`: passed
- `uv run ty check src`: passed
- `openspec validate polish-experimental-textual-tui --type change --strict`:
  passed

## Remaining Open Items

### Code Structure

- Extract focused TUI modules for transcript behavior, tool widgets, command
  handling, screens, and prompt history. This is a maintainability follow-up,
  not a current behavior blocker.

### Diff Layout

- Decide whether optional wide-layout diff behavior is worth implementing.
- Keep single-column diff as the default and supported fallback.

### Manual Verification

- macOS manual validation for the current pass has been completed.
- Manually verify `deepy tui` on Windows Terminal with PowerShell 7 before
  treating the TUI as release-ready.
- During Windows verification and any future regression pass, check:
  - long prompts and prompt resizing
  - side-panel toggle behavior
  - prompt submission while scrolled into transcript history returns to the
    bottom for the new turn
  - while a long model turn is still streaming, scrolling up preserves the
    reading position and shows `New output below` when later output arrives
  - narrow terminal layout
  - wide terminal layout
  - live tool output growth
  - AskUserQuestion keyboard flow
  - `/sessions` and `/resume`
  - `/compact`
  - diff hunk navigation and folding
  - unsupported `/init` and `/reset` messages
  - no accidental support claim for `!command` local shell command mode
  - current TUI skill command boundary versus stable UI skill market behavior

### Next-Version Feature Gaps

- Add real TUI support for `/init` if AGENTS.md initialization should be
  available without leaving the experimental app.
- Add real TUI support for `/reset` if config reset/setup should be available
  without leaving the experimental app.
- Decide and implement the TUI-local command strategy for `!command` execution,
  including transcript persistence, interruption, exit-code display, and
  cross-platform behavior.
- Connect skill market and full skill management to the TUI, including market
  search, install, update, uninstall, installed-skill state, and a first-class
  Textual management surface.

## Release Readiness Bar

Before archiving or releasing this TUI polish change:

- Complete or explicitly defer the module extraction item.
- Decide whether wide-layout diff is in scope or intentionally deferred.
- Keep the completed macOS manual checklist as the regression baseline.
- Run Windows Terminal with PowerShell 7 manual verification.
- Re-run:
  - `uv run pytest -q`
  - `uv run ruff check`
  - `uv run ty check src`
  - `openspec validate polish-experimental-textual-tui --type change --strict`

## Current Recommendation

Treat the TUI as broadly aligned with stable `deepy` for core day-to-day
workflows after the completed macOS validation. The main remaining intentional
parity gaps are `/init`, `/reset`, user-entered `!command` local shell command
mode, and skill market/full skill management. These should be planned for the
next version unless they are explicitly accepted as stable-UI-only features.

Before archive or release, finish Windows Terminal with PowerShell 7
verification and decide whether module extraction and optional wide diff layout
are release blockers or deferred maintainability work.
