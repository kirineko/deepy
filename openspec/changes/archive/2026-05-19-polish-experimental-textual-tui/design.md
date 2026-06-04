## Context

Deepy currently has two terminal experiences:

- `deepy`: the stable Rich and prompt-toolkit UI.
- `deepy tui`: an opt-in experimental Textual app under `src/deepy/tui/`.

The experimental TUI already starts, submits normal prompts, consumes
`DeepyStreamEvent`, renders Markdown, displays live thinking/tool blocks, keeps
`session_id` between turns, summarizes `load_skill`, and renders Deepy-owned
diff previews. After the current polish pass, it also has command discovery,
AskUserQuestion continuation, session/context commands, richer tool widgets,
controlled auto-scroll, prompt history, and diff navigation. The remaining
stable UI parity work is concentrated in `/init`, `/reset`, user-entered
`!command` local command mode, and skill market/full skill management.

Reference projects show useful patterns but should not be copied wholesale:

- Textual provides first-class primitives for command providers, modal screens,
  tabbed content, selection lists, data tables, markdown viewers, headless
  `run_test`, and responsive CSS.
- Toad demonstrates conversation block navigation, collapsible tool calls,
  embedded question UI, side panels, session screens, and prompt-adjacent
  completion surfaces.
- Toad and `textual-diff-view` remain references only. This change keeps Deepy's
  runtime dependencies and diff implementation under Deepy ownership.

## Goals / Non-Goals

**Goals:**

- Make `deepy tui` feel like a coherent Textual application rather than a
  minimal transcript wrapper.
- Close the user-visible continuation gap for AskUserQuestion.
- Add Textual-native screens or modals for high-value slash commands.
- Bring session resume, new session, and manual compaction into the TUI.
- Bring `/init`, `/reset`, local command mode, and skill market/full skill
  management into the TUI.
- Give shell, read, todo, MCP, web, and question outputs dedicated readable
  treatments without changing model-facing tool contracts.
- Improve transcript navigation, block expansion, auto-scroll behavior, input
  history, and resize handling.
- Preserve default `deepy` behavior and keep the TUI opt-in.

**Non-Goals:**

- Do not make `deepy tui` the default interactive UI.
- Do not vendor Toad, `textual-diff-view`, or AGPL code.
- Do not redesign provider, tool, or session storage protocols.
- Do not build a general settings center beyond the configuration reset/setup
  fields required for `/reset`.
- Do not add a Windows terminal emulator, PTY layer, or `pywinpty` dependency
  for TUI local command mode.
- Do not require a new runtime dependency unless a later implementation proves
  it is necessary and license-compatible.

## Decisions

### 1. Keep the shared runner boundary

The TUI will continue invoking the existing `run_prompt_once()` path and
consuming normalized `DeepyStreamEvent` values. TUI widgets must not depend on
provider SDK event objects.

Alternatives considered:

- Directly integrate provider streams in Textual widgets. Rejected because it
  duplicates runner behavior and weakens compatibility with the stable UI.
- Fork a TUI-specific tool runner. Rejected because tool semantics, session
  persistence, and interruption behavior must stay shared.

### 2. Split the TUI into app shell, screens, widgets, and adapters

The current `DeepyTuiApp` can remain the coordinator, but new behavior should be
split into focused modules:

- `screens.py` or `screens/`: help/status, sessions, skills, model/theme, MCP,
  and question surfaces.
- `tool_widgets.py`: shell, read, todo, web, MCP, question, and generic tool
  blocks.
- `transcript.py`: block cursor, expand/collapse behavior, controlled
  auto-scroll, transcript restoration.
- `commands.py`: Textual command palette providers and slash command dispatch.
- `history.py`: prompt input history and restored drafts.

This keeps implementation reviewable and prevents `app.py` from becoming the
entire TUI.

### 3. Use Textual command palette plus slash commands

Slash commands remain valid in the prompt, but command discovery should also use
Textual command providers. `/` suggestions should be fast prompt-adjacent
completion; command palette should be the richer navigable surface for commands,
categories, and descriptions.

Alternatives considered:

- Only improve `/` suggestions. Rejected because it still hides category,
  command help, and argument forms in a flat completion list.
- Only use command palette and drop slash commands. Rejected because slash
  commands are already part of Deepy's stable terminal contract.

### 4. Prefer embedded AskUserQuestion over plain transcript summary

AskUserQuestion will render a question surface tied to the pending turn. It may
be a modal or prompt-adjacent embedded surface, but it must:

- focus automatically when the turn enters waiting-for-user state,
- support single select, multi-select, custom answer, and cancellation,
- submit answers back through the same session continuation path,
- preserve the question and selected answer in transcript history.

For usability, the implementation should prefer a prompt-adjacent embedded
surface when it fits; a modal is acceptable for narrow terminals or complex
multi-question prompts.

### 5. Tool widgets are summary-first and expandable

Tool blocks should present a concise header with name, state, path or target,
and important metadata. Full output belongs behind expand/collapse or in a
dedicated detail region.

Default expansion policy:

- shell failures and waiting-for-user states expand automatically,
- successful shell/read/web output stays summarized unless short,
- todo updates project to the side panel and records a transcript summary,
- file diffs render as separate diff blocks tied to their tool result.

This follows the useful part of Toad's tool-call model without copying its
implementation.

### 6. Diff improvements stay Deepy-owned

The existing Rich-backed diff preview remains the base. This change adds hunk
modeling, wrapping, hunk folding, hunk navigation, and wide/narrow behavior.
Side-by-side diff is optional and should only be implemented if the terminal is
wide enough and the underlying model can keep the single-column fallback clean.

### 7. Controlled auto-scroll is a state machine

Auto-scroll should not always force `scroll_end`. The transcript should track
whether the user is anchored near the bottom:

```text
Anchored at bottom
  | user scrolls up
  v
Reading history  -- new output --> show "new output" indicator
  | user presses End / prompt submit / clicks indicator
  v
Anchored at bottom
```

Live blocks may request scroll only while anchored. This prevents long tool
output or thinking deltas from fighting the user's manual scroll position.

### 8. Responsive layout uses feature degradation

Wide terminals may show transcript plus side panel. Narrow terminals should
favor a clean single-column transcript and open auxiliary surfaces as modal
screens. Text must wrap or fold inside its container; UI elements must not
overlap.

### 9. Stable UI parity is the completion target for this pass

The earlier transition policy allowed stable slash commands to show explicit
TUI-specific unsupported messages. That was useful during the first polish pass,
but this follow-up should now implement the remaining meaningful stable UI
contracts:

- `/init` starts the existing AGENTS.md initialization model prompt inside the
  active TUI session.
- `/reset` opens a Textual-native configuration reset/setup flow.
- `!command` runs as local command mode rather than a model turn.
- `/skills` connects to the full local/market skill management surface.

Unsupported messages should remain only for command forms that are explicitly
out of scope or unsafe in a Textual full-screen app.

### 10. `/init` reuses the model-turn path

The TUI should not create a separate AGENTS.md writer. It should reuse
`build_agents_init_prompt(project_root, extra_instruction=...)` and then submit
that generated prompt through the same model-turn path used by normal prompts.
The transcript should preserve the user-visible `/init ...` command, while the
model receives the repository-analysis initialization prompt.

### 11. `/reset` is a Textual configuration flow

The stable UI reset command deletes the current TOML config and then invokes a
prompt-toolkit setup flow. The TUI should not nest prompt-toolkit prompts inside
Textual. Instead, it should provide a Textual modal/screen that collects the
same durable fields:

- API key,
- model,
- base URL,
- UI theme.

On submit, the TUI should call the existing `write_config()` helper and reload
settings from the same config path. If the config path is unknown or points to
an unsupported JSON config, the TUI should render a clear error and keep the
current app state recoverable.

### 12. TUI local command mode reuses existing local command helpers

Stable local command mode already has a reusable implementation in
`src/deepy/ui/local_command.py`:

- `parse_local_command()` detects prompts whose trimmed text starts with `!`;
- `run_local_command()` executes the command using platform-aware runtime
  detection;
- `shell_tool_result_json()` converts the result into the same shell
  `ToolResult` JSON shape used by tool rendering;
- `build_synthetic_shell_transcript_items()` persists the literal `!` input,
  synthetic shell call, and synthetic shell output into session history.

The TUI should call these helpers rather than implementing a second local shell
runner. The result should render through the existing TUI shell `ToolBlock`
treatment, update the active session id when a new session is created for the
local command, and never send the `!command` text to the model.

### 13. Preserve the existing Windows local-command boundary

Windows support for `!command` in the TUI should follow the current stable local
command boundary, not invent a terminal emulator:

```text
TUI prompt "!..."
        |
        v
parse_local_command()
        |
        v
run_local_command()
        |
        +-- POSIX  -> PTY-backed shell
        |
        +-- Windows -> subprocess pipes
                       stdin=DEVNULL
                       stdout/stderr captured
                       no pywinpty
                       no shell=True
                       no interactive editor/pager/full-screen support
```

The current Windows path prepares Python UTF-8 environment values, invokes the
detected shell with dialect-specific arguments, captures output through pipes,
decodes Windows-compatible output, normalizes line endings, strips terminal
control sequences, and reports metadata such as shell kind, command dialect,
TTY mode, cwd, exit code, duration, timeout, and interruption state.

PowerShell and PowerShell Core should be supported through that existing
pipe-based path. The implementation does not need to add special interactive
support for `cmd.exe`; if the detected Windows shell path is not supported by
the TUI implementation, the TUI must show an explicit unsupported message and
must not submit the command as a model prompt. Reusing the existing `cmd`
dialect path is acceptable if it keeps the same non-interactive pipe boundary.

### 14. Skill management gets a real Textual surface

The current TUI local skill commands are too shallow for parity. The follow-up
should keep simple subcommands working in the transcript, but `/skills` without
arguments should open a Textual management surface with installed/local and
market views. The surface should support viewing skill details without dumping
full `SKILL.md` bodies into the main transcript, and should route market
actions through existing `skill_market.py` helpers.

## Risks / Trade-offs

- AskUserQuestion continuation may touch runner/session behavior -> Mitigate by
  reusing existing `RunSummary.pending_questions` and stable UI continuation
  logic instead of adding a TUI-only protocol.
- Textual screens can fragment state -> Mitigate by keeping session, settings,
  loaded skills, and pending question state in `DeepyTuiApp` or a small shared
  state object and passing callbacks into screens.
- Command parity can balloon scope -> Mitigate by limiting this pass to the
  known remaining parity gaps: `/init`, `/reset`, `!command`, and skill
  market/full skill management.
- Windows local command behavior can corrupt prompt input if terminal control
  sequences leak -> Mitigate by reusing the existing Windows pipe path,
  sanitization, and metadata tests instead of allocating a Windows PTY.
- `/reset` can conflict with Textual focus and prompt state if implemented by
  calling prompt-toolkit -> Mitigate by implementing a Textual-native config
  form and reusing only config persistence helpers.
- Large outputs can degrade Textual performance -> Mitigate with truncation,
  expandable details, batching of high-frequency deltas, and headless stress
  tests.
- Windows Terminal and PowerShell behavior may differ -> Mitigate with manual
  verification tasks and by preserving the stable UI fallback.
- Shared helper refactors may regress the stable UI -> Mitigate with existing
  terminal UI tests plus targeted regression tests for shared message and tool
  formatting helpers.

## Migration Plan

1. Keep `deepy tui` behind the existing explicit subcommand.
2. Add TUI screens/widgets incrementally behind the experimental path.
3. Preserve existing stable UI tests and add Textual `run_test` coverage for new
   surfaces.
4. Validate local command mode through headless tests for POSIX and simulated
   Windows PowerShell/cmd runtime paths.
5. Validate on macOS first, then manually verify Windows Terminal with
   PowerShell 7 before considering broader release messaging.
6. Rollback is straightforward: keep the default `deepy` path unchanged and
   revert the experimental TUI change if needed.

## Open Questions

- Should AskUserQuestion default to an embedded prompt-adjacent surface on all
  terminals, or use a modal by default for clearer focus?
- Should side-by-side diff ship in this change or remain a follow-up after
  wrapping, folding, and hunk navigation are stable?
- Which MCP status details are stable enough to expose in the TUI without
  committing to an internal server schema too early?
