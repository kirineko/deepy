# Deepy TUI Next Version Checklist

Date: 2026-05-19

This document summarizes what the experimental `deepy tui` supports today and
what remains before it reaches feature parity with the stable `deepy` terminal
UI. It is the handoff document for the next TUI iteration after archiving the
`add-experimental-textual-tui` OpenSpec change.

## Current Status

`deepy tui` is an opt-in experimental Textual app. It does not replace the
stable Rich and prompt-toolkit UI started by `deepy`.

The current TUI is usable for normal model turns, basic skill loading, live
thinking/tool display, and colored write/modify diffs. It is not yet feature
complete relative to the stable UI, especially around slash commands,
AskUserQuestion continuation, shell/todo-specific surfaces, MCP status, session
management, and mature auxiliary views.

## Implemented

### Entry And Compatibility

- `deepy tui` CLI command starts the experimental Textual app.
- The default `deepy` command still starts the stable Rich/prompt-toolkit UI.
- Textual is added with a Python 3.12-compatible dependency range.
- The TUI code lives in `src/deepy/tui/`, parallel to `src/deepy/ui/`.
- Toad and `textual-diff-view` are reference-only; they are not imported,
  vendored, or added as dependencies.
- Startup failure falls back to a concise terminal error that points users back
  to `deepy`.

### App Shell And Input

- Textual layout with header, transcript, status bar, prompt area, footer, and a
  collapsible side status panel.
- Experimental startup hint without labeling it as a user message.
- Theme mapping for Deepy's `auto`, `dark`, and `light` settings through
  Textual themes.
- Enter submits; Shift+Enter inserts a newline.
- Ctrl+D twice exits; `/exit` and `/quit` exit without starting a model turn.
- Escape requests interruption during a running model turn.
- Ctrl+O toggles the side status panel.
- Alt+Up and Alt+Down move focus between transcript blocks.
- Slash command suggestions appear when typing `/`.
- `@file` suggestions use existing project file mention matching.
- Transcript auto-scrolls as new blocks are appended and as live thinking,
  assistant, or tool blocks grow.
- The app keeps `session_id` between turns, so the second prompt continues the
  same conversation context.

### Runner And Stream Integration

- The TUI invokes the existing `run_prompt_once()` path in a Textual worker.
- TUI widgets consume normalized `DeepyStreamEvent` values instead of provider
  SDK objects.
- Assistant text is rendered as Textual Markdown.
- Reasoning deltas render as live `Thinking` blocks.
- Tool calls render as running blocks and update when output arrives.
- Final assistant output is ordered after thinking/tool blocks, matching actual
  stream order instead of jumping ahead.
- Duplicate final `message` events are ignored when equivalent text deltas were
  already streamed.
- Usage appears as a compact one-line transcript item rather than a large block.
- Errors render as readable error blocks.

### Tool Rendering

- All existing Deepy function tools remain available to the model through the
  shared runner: `shell`, `AskUserQuestion`, `read`, `modify`, `WebSearch`,
  `WebFetch`, `load_skill`, and `todo_write`.
- TUI tool execution does not use a separate tool implementation; it consumes
  the same JSON `ToolResult` payloads via `parse_tool_output()`.
- Tool parameters are summarized with the existing `message_view` helpers.
- Tool output is compacted to avoid dumping very long raw content.
- `load_skill` output is summarized by skill name, description, and root instead
  of printing the full `SKILL.md` body.
- `write`, `modify`, and legacy `edit` outputs produce a Deepy-owned diff view.
- Diff rendering now reuses the existing Rich diff renderer, including line
  gutters, added/removed colors, and syntax highlighting.
- Large diffs are truncated in the TUI diff model.

### Implemented Slash Command Behavior

- `/exit` and `/quit`: exit the TUI.
- `/skills list` and `/skills`: list available skills in the transcript.
- `/skills use NAME`: load a skill for subsequent prompts without printing the
  full skill body.
- `/skills show NAME`: show basic skill metadata.
- `/skill:NAME [prompt]`: invoke one skill for a model turn.

### Tests

- Headless Textual startup/exit tests.
- Prompt tests for Enter, Shift+Enter, slash suggestions, and file mentions.
- Session continuity test for passing `session_id` between turns.
- Stream rendering tests for assistant output, thinking, tool calls, tool
  output, diffs, usage, and errors.
- Regression test for duplicate streamed output.
- Regression test for transcript auto-scroll while a live block grows.
- Diff tests for write/modify recognition, syntax/color rendering, truncation,
  and AGPL reference package avoidance.
- Legacy UI regression tests remain in the full suite.

## Missing Feature Parity

### Slash Commands

The stable UI supports many slash commands that the TUI only suggests or does
not expose at all.

Not implemented in TUI:

- `/help`: no dedicated help screen or command output.
- `/new`: does not clear current session or reset loaded skills.
- `/resume [ID]`: no session picker and no session resume flow.
- `/sessions`: no session list view.
- `/status`: no full project status report view.
- `/mcp`: no MCP server/tool status view.
- `/compact [focus]`: no active session compaction flow.
- `/model`, `/model list`, `/model set ...`, `/model reasoning ...`: no model
  picker or persisted model/reasoning settings flow.
- `/theme [auto|dark|light]`: no persisted theme update flow.
- `/reset`: no config reset/setup flow.
- `/init`: no AGENTS.md initialization flow.

Partially implemented:

- `/skills`: basic list/use/show exists, but no Textual skills screen.
- `/skills search`, `/skills install`, `/skills uninstall`,
  `/skills installed`, `/skills update NAME`, `/skills update --all`: missing.
- `/skills show NAME`: currently shows metadata only, not a polished markdown
  skill detail window.
- `/skill:NAME`: invokes a skill, but does not yet share the stable UI's full
  clarification loop behavior.

Also missing:

- Slash suggestion selection is simple first-match Tab acceptance; there is no
  rich command palette, grouped command categories, or per-command forms.

### Tool-Specific Surfaces

The model can call all tools, but several tools still render through generic
compact output instead of first-class TUI widgets.

Missing or partial:

- `shell`: no dedicated shell output block with command, exit code, stdout,
  stderr, duration, wrapping, copy support, or large-output navigation.
- `todo_write`: no todo board or side-panel projection using existing todo
  metadata.
- `AskUserQuestion`: pending questions are stored and summarized, but there is
  no interactive Textual question view for options, multi-select, custom answer,
  cancellation, or continuation.
- `WebSearch`: no search-result cards, source list, or expandable result body.
- `WebFetch`: no URL metadata card beyond compact parameter/output text.
- `read`: no file preview widget with syntax highlighting or large file
  folding.
- MCP tool calls: no MCP-specific output normalization beyond generic tool
  rendering and no MCP status/cleanup UI.
- Tool waiting-for-user state: no dedicated visual treatment beyond generic
  tool status text.
- Tool expand/collapse: the base block binding exists, but large hidden-detail
  models are not yet implemented.

### Diff Surface

Implemented:

- Unified diff model for `write`, `modify`, and `edit`.
- Added/removed colors, line gutters, syntax highlighting, path summary, and
  truncation.

Still missing:

- Terminal-width wrapping for long changed lines.
- Hunk headers and hunk-level folding controls in the interactive widget.
- File summary for multi-file or future multi-hunk outputs.
- Side-by-side diff mode for wide terminals.
- Keyboard actions for next/previous hunk, copy path, copy hunk, or open file.
- Visual tests for narrow and wide terminal widths.

### Conversation And Session Flow

Missing:

- Interactive AskUserQuestion clarification loop after `waiting_for_user`.
- `/resume` and `/sessions` views.
- `/new` session reset.
- `/compact` context compaction.
- Exit summary parity with the stable UI.
- Transcript restoration from previous sessions.
- Input history navigation.
- Copy/select/export actions for transcript blocks.
- A clearer distinction between visible assistant text and hidden reasoning in
  configurations where reasoning should be minimized.

### Auxiliary Views

Missing:

- Full status/help view with model, reasoning mode, project root, active
  session, MCP status, loaded skills, keybindings, and config path.
- Model/reasoning picker.
- Theme picker.
- Sessions picker.
- Skills browser with installed/market tabs and markdown detail view.
- AskUserQuestion modal/screen.
- Settings/config reset/setup screens.

### Performance And Robustness

Missing:

- Batching or throttling for high-frequency text and reasoning deltas.
- Backpressure strategy for very large tool outputs.
- More careful auto-scroll behavior when the user has intentionally scrolled up.
- Windows Terminal and PowerShell 7 manual verification.
- Richer resize tests for narrow/mobile-like terminal widths and wide layouts.
- More direct tests for interruption and cancellation cleanup.

## Suggested Next Version Scope

Recommended next version focus:

1. Implement AskUserQuestion continuation as a Textual modal or screen.
2. Add session and context commands: `/new`, `/resume`, `/sessions`, `/compact`.
3. Add first-class tool widgets for `shell`, `todo_write`, and `read`.
4. Build a real `/skills` screen with installed/market tabs and markdown detail.
5. Add `/model`, `/theme`, `/status`, and `/mcp` views.
6. Improve diff interactivity: wrapping, hunk folding, hunk navigation, and
   optional side-by-side view.
7. Add input history, user-controlled auto-scroll behavior, and high-frequency
   stream throttling.
8. Run manual verification on macOS, Linux, and Windows Terminal with
   PowerShell 7.

## Acceptance Bar For Next Iteration

- All stable slash commands either work in TUI or show a clear "not supported in
  TUI yet" message.
- AskUserQuestion can complete a real pending-question turn without leaving the
  TUI.
- Shell, todo, read, write, modify, WebSearch, WebFetch, load_skill, and MCP
  outputs each have readable TUI treatment.
- Session resume, new session, and compaction work without returning to the
  stable UI.
- TUI tests cover the new views with Textual Pilot/headless helpers.
- Full suite passes: `uv run pytest -q`, `uv run ruff check`, `uv run ty check
  src`, and OpenSpec strict validation.
