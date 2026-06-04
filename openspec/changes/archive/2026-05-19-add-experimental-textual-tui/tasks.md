## 1. Dependency And CLI Entry

- [x] 1.1 Choose a Python 3.12-compatible Textual dependency constraint and add it to project metadata without importing toad or textual-diff-view
- [x] 1.2 Add `deepy tui` CLI parsing and dispatch while keeping `deepy` default interactive behavior unchanged
- [x] 1.3 Add CLI help text that marks `tui` as experimental
- [x] 1.4 Add CLI tests proving `deepy tui` dispatches to the TUI runner and `deepy` still dispatches to the existing interactive UI
- [x] 1.5 Add a dependency/license note in code or docs stating that toad and textual-diff-view are references only and must not be copied or depended on in this change
- [x] 1.6 Remove stale `src/deepy/ui/tui/` artifacts and keep new Textual code in the parallel `src/deepy/tui/` package

## 2. Textual App Foundation

- [x] 2.1 Create a new Textual app module with a minimal app class, startup screen, theme loading, and clean exit path
- [x] 2.2 Create a conversation screen layout with transcript region, prompt region, status/footer region, and room for optional side/modal views
- [x] 2.3 Map existing Deepy `auto`, `dark`, and `light` UI themes to readable Textual/TCSS styles
- [x] 2.4 Add experimental labeling to startup/help without repeating it on every transcript block
- [x] 2.5 Add a fallback startup error path that prints an actionable message and leaves the legacy UI available

## 3. Prompt And Navigation

- [x] 3.1 Implement a Textual-native prompt widget with Enter submit and Shift+Enter newline behavior
- [x] 3.2 Implement Ctrl+D or equivalent quit confirmation for the TUI
- [x] 3.3 Add slash command discovery for existing Deepy slash commands in a selectable Textual surface
- [x] 3.4 Add initial `@file` mention affordance using Deepy's existing project-file matching logic where practical
- [x] 3.5 Add keyboard navigation between transcript blocks and a visible focus state
- [x] 3.6 Add expand/collapse actions for blocks with hidden details

## 4. Runner Event Bridge

- [x] 4.1 Add a Textual worker or async bridge that invokes `run_prompt_once()` without blocking UI responsiveness
- [x] 4.2 Forward normalized `DeepyStreamEvent` values from the runner into the app without exposing provider-specific event objects to widgets
- [x] 4.3 Track busy state, active session id, usage, and pending questions in TUI state
- [x] 4.4 Add interrupt handling for a running model turn using existing runner cancellation semantics
- [ ] 4.5 Batch or throttle high-frequency text and reasoning deltas to avoid flooding Textual refreshes

## 5. Transcript Widgets

- [ ] 5.1 Implement user prompt blocks with Markdown-compatible rendering and stable transcript insertion
- [x] 5.2 Implement assistant Markdown blocks with readable headings, lists, code fences, tables, links, and inline emphasis
- [x] 5.3 Implement thinking blocks with a distinct visual style and live update support
- [x] 5.4 Implement tool call blocks with pending, in-progress, completed, failed, and waiting-for-user states
- [ ] 5.5 Implement shell output blocks that render captured output readably without introducing interactive PTY support
- [ ] 5.6 Implement todo update blocks or side-panel projection using existing todo metadata parsing
- [x] 5.7 Implement usage and status summary blocks for completed turns
- [x] 5.8 Implement error blocks that keep exception text readable and selectable

## 6. Diff Surface

- [x] 6.1 Define a Deepy-owned diff view model from existing write/modify tool metadata
- [ ] 6.2 Implement unified diff rendering with file path, hunk context, line gutters, added and removed line styling, and terminal-width wrapping
- [x] 6.3 Add hunk folding or compact rendering for large diffs
- [ ] 6.4 Add a wide-terminal side-by-side diff mode only if unified diff behavior is already stable
- [x] 6.5 Add tests proving the diff surface does not import or depend on toad or textual-diff-view

## 7. Auxiliary Screens And Flows

- [ ] 7.1 Add a sessions view that lists previous sessions and returns to the conversation after selection or cancellation
- [ ] 7.2 Add a skills view that can browse installed and market skills using existing Deepy skill models
- [ ] 7.3 Add an AskUserQuestion view that supports predefined options, custom answer, and multi-select behavior
- [ ] 7.4 Add a status/help view for model, reasoning mode, project root, active session, MCP status, and key bindings
- [ ] 7.5 Ensure auxiliary views close back to the active conversation without losing prompt or transcript state

## 8. Testing And Verification

- [x] 8.1 Add Textual headless startup and exit tests
- [x] 8.2 Add Textual prompt tests for Enter submit, Shift+Enter newline, slash discovery, and file mention insertion
- [x] 8.3 Add Textual stream-event tests for assistant output, thinking, tool call updates, tool output, usage, and errors
- [ ] 8.4 Add Textual diff tests for narrow and wide terminal widths
- [ ] 8.5 Add Textual AskUserQuestion tests for option selection, custom answer, and cancellation paths
- [x] 8.6 Add regression tests proving existing Rich/prompt-toolkit UI behavior remains unchanged for default `deepy`
- [x] 8.7 Run focused tests for CLI, prompt input, terminal UI, message view, runner event normalization, and new TUI modules
- [x] 8.8 Run full `uv run pytest -q`, `uv run ruff check`, and the configured type checker before marking implementation complete

## 9. Documentation And Release Readiness

- [x] 9.1 Document `deepy tui` as experimental and opt-in
- [x] 9.2 Document known limitations, especially no first-iteration interactive shell/PTY and no AGPL reference-code dependency
- [x] 9.3 Add a short feedback path or issue template note for users trying the experimental TUI
- [x] 9.4 Verify packaging includes any Textual TCSS/assets needed by the app
- [x] 9.5 Validate the OpenSpec change with strict checks before implementation sign-off
