## Context

Deepy's current interactive path is intentionally conservative: prompt-toolkit
owns input, Rich owns completed transcript output, and the current terminal UI
spec protects stable behavior for Enter, Shift+Enter, Ctrl+D, themes, thinking, tool
summaries, session resume, model selection, skills, and status. That UI must
remain the default because users rely on it and because recent terminal-bottom
work showed how fragile mixed renderer ownership can be.

The project now has the right internal boundary for an experimental TUI:
`run_prompt_once()` already emits normalized `DeepyStreamEvent` values for
text, reasoning, tool calls, tool output, status, and usage. Deepy also has
plain Python models for skills, sessions, status, pending questions, and tool
output parsing. A Textual app can subscribe to those model and event boundaries
without changing provider, tool, session, or prompt semantics.

The reference direction is toad's Textual architecture: a long-lived app with
Screens, reactive conversation widgets, focusable transcript blocks, a prompt
TextArea, live tool widgets, and a visually rich diff surface. The constraint is
licensing and compatibility: toad is AGPL and Python 3.14-oriented, and
`textual-diff-view` is also AGPL. Deepy should learn from those interaction
patterns but own its implementation and keep Python 3.12 support.

## Goals / Non-Goals

**Goals:**

- Add `deepy tui` as an opt-in experimental Textual UI.
- Keep `deepy` and the existing Rich/prompt-toolkit UI unchanged by default.
- Use Textual's app model for a richer experience: full-screen layout, TCSS
  themes, focusable/navigable transcript blocks, live progress, subtle
  animation, side panels, modal screens, and keyboard command discovery.
- Reuse Deepy's existing runner, stream events, sessions, tools, skills,
  AskUserQuestion models, and config where practical.
- Add a Deepy-owned diff widget for write/modify previews with unified and
  narrow-friendly layouts, syntax coloring where available, and no AGPL code.
- Add tests that exercise Textual widgets in headless mode and preserve legacy
  UI behavior.
- Keep dependency choices compatible with Python 3.12.

**Non-Goals:**

- Do not replace the default `deepy` interactive UI.
- Do not copy toad source code or import toad as a runtime dependency.
- Do not depend on `textual-diff-view` unless a later licensing decision
  explicitly changes that boundary.
- Do not require Python 3.14, Rich 15, or toad's dependency set.
- Do not build a fully interactive embedded shell/PTY in the first iteration.
  Local command output may be rendered richly, but toad-style interactive shell
  emulation is a later separate proposal.
- Do not change model provider behavior, tool schemas, session JSONL format, or
  existing slash command semantics for the legacy UI.

## Decisions

1. Build a separate Textual entrypoint behind `deepy tui`.

The experimental app should live beside the current UI, not inside it. The new
package boundary is `src/deepy/tui/`, parallel to `src/deepy/ui/`. The CLI can
dispatch `deepy tui` to a Textual app runner while existing `deepy` dispatch
continues to call the current interactive loop. This makes rollback trivial and
lets the TUI move faster without destabilizing users who did not opt in.

   Alternative considered: replace the current interactive loop in place. This
   was rejected because Textual and prompt-toolkit own terminal input/output in
   different ways, and a full replacement would make regressions harder to
   isolate.

2. Use Deepy's stream-event boundary as the Textual adapter contract.

   The Textual app should not know OpenAI Agents SDK event shapes directly. A
   runner worker invokes `run_prompt_once()` and forwards `DeepyStreamEvent`
   values into the app. The app then updates reactive UI state and appends or
   mutates transcript widgets. This preserves the current provider/tool/session
   architecture and keeps visual code focused on presentation.

   Alternative considered: create a TUI-specific runner. This was rejected
   because it would duplicate cancellation, compaction, usage, pending-question,
   and session logic.

3. Keep text input Textual-native.

   The TUI prompt should use a Textual `TextArea`-based widget rather than
   embedding prompt-toolkit. It should preserve Deepy's mental model: Enter
   submits, Shift+Enter inserts a newline, Ctrl+D exits with confirmation, slash
   commands are discoverable, and `@file` mention support remains available.
   The implementation can port Deepy's current file mention and slash command
   logic into Textual widgets over time.

   Alternative considered: keep prompt-toolkit for input and render Textual
   above it. This was rejected because two long-lived terminal UI systems would
   recreate renderer ownership conflicts.

4. Model the transcript as focusable blocks.

   The core UX improvement should be a navigable conversation timeline:
   submitted prompts, assistant Markdown, thinking, tool calls, todo updates,
   diffs, shell output, AskUserQuestion cards, errors, and usage summaries are
   individual blocks. Blocks can expose actions such as expand/collapse,
   copy/extract text, focus next/previous, and maximize details. This is where
   Textual provides a clear advantage over one-way Rich scrollback.

   The app should emphasize visual hierarchy and motion carefully: subtle busy
   indicators, transient flash messages, animated progress accents, collapsible
   detail panels, and responsive layout transitions. It should not add
   decorative noise that reduces terminal readability.

5. Create a Deepy-owned diff surface.

   The first diff widget should parse the existing diff metadata produced by
   write/modify tools and render a unified diff layout with gutters, added and
   removed lines, file summary, folding for long hunks, and responsive wrapping.
   A later iteration can add side-by-side layout if the terminal is wide enough.
   The design may imitate the usability goals of toad and textual-diff-view, but
   the code and dependency graph remain Deepy-owned unless licensing changes.

6. Treat experimental status as a product and UI state.

   `deepy tui` should show experimental labeling in the startup screen and help
   surface, but should avoid nagging inside every interaction. Errors should
   fail back to a normal terminal with actionable messages. The legacy UI should
   remain available as the supported fallback.

7. Use Textual tests as acceptance gates.

   Textual's `run_test()` and Pilot can validate key flows headlessly: startup,
   prompt submit, newline insertion, stream event rendering, tool expand/collapse,
   diff rendering, question selection, session list navigation, and theme
   application. Existing unit tests should continue proving legacy Rich output
   and prompt-toolkit behavior.

## Risks / Trade-offs

- [Risk] Textual dependency churn or version constraints conflict with Deepy's
  package baseline. -> Mitigation: choose a Python 3.12-compatible Textual
  constraint, avoid toad's pinned stack, and keep `deepy` functional even if
  experimental TUI code is not invoked.
- [Risk] The TUI duplicates rendering logic from `message_view.py`. ->
  Mitigation: reuse parsing/model helpers first, then split pure view models
  from Rich-specific renderables only when duplication becomes real.
- [Risk] Streaming updates can flood Textual's message pump. -> Mitigation:
  batch high-frequency text deltas, throttle refreshes, and use Textual workers
  for runner execution.
- [Risk] Experimental animation may reduce performance or readability. ->
  Mitigation: keep animation subtle, disable it in test/headless mode, and make
  dense transcript readability the acceptance gate.
- [Risk] Windows behavior differs from macOS/Linux terminals. -> Mitigation:
  rely on Textual's supported terminal abstractions for the app shell, keep
  shell/PTY emulation out of the first iteration, and add platform-aware tests
  for key bindings and fallback errors.
- [Risk] AGPL contamination from reference code. -> Mitigation: do not copy
  toad or textual-diff-view code, do not vendor those packages, and document the
  license boundary in tasks and review checklist.

## Migration Plan

1. Remove the stale `src/deepy/ui/tui/` experiment and keep the new Textual
   package under `src/deepy/tui/`.
2. Add Textual dependency and CLI parser support for `deepy tui`.
3. Introduce a minimal Textual app shell that can start, render welcome/status,
   accept input, and exit cleanly.
4. Add a runner worker adapter that forwards `DeepyStreamEvent` values into the
   app without changing `run_prompt_once()`.
5. Build transcript block widgets for user input, assistant Markdown, thinking,
   tool calls, shell output, todo updates, diffs, errors, usage, and questions.
6. Add keyboard navigation, help/footer, slash command discovery, and file
   mention affordances.
7. Add headless Textual tests and legacy regression tests.
8. Keep the feature marked experimental in docs/help until real terminal testing
   on macOS, Linux, and Windows confirms the interaction model.

Rollback is simple while the feature is opt-in: remove or hide the `deepy tui`
command and leave the default `deepy` path untouched.

## Open Questions

- Should `deepy tui` support a compact single-column default first, or expose a
  side panel for todos/sessions/status in the initial version?
- Should assistant text stream live as Markdown blocks during generation, or
  appear as a stable Markdown block after the turn completes while live progress
  focuses on thinking/tool/status?
- Should side-by-side diffs be included in the first implementation, or delayed
  until unified diff behavior is polished?
- Which parts of TUI configuration belong in existing `[ui]` config versus an
  experimental `[tui]` subsection?
