## Context

Deepy's interactive UI currently has three terminal renderers active across a
single turn:

- prompt-toolkit owns idle input and the prompt footer.
- Rich prints user echo, thinking, tool output, assistant output, and usage
  into normal scrollback.
- `_TerminalBottomStatus` uses ANSI scroll regions for model/local-command
  runtime status and footer rows.

This split is fragile at the terminal bottom. Recent testing showed that local
patches such as adding blank prompt rows, pre-scrolling, or drawing an idle
footer outside prompt-toolkit either had no effect or created new rendering
bugs. The follow-up architecture should move idle and running interaction into
one prompt-toolkit-owned surface, using the current ANSI helper only as a
temporary fallback until it can be removed.

The reference implementation in `reference/kimi-cli` points to the shape:
`CustomPromptSession` owns prompt message, bottom toolbar, running delegates,
and invalidation; running views render live status into the prompt message area
instead of competing with prompt-toolkit from outside.

## Goals / Non-Goals

**Goals:**

- Make prompt-toolkit the single owner of idle prompt input and footer layout.
- Preserve the compact footer content and visual hierarchy.
- Preserve a runtime status/progress delegate shape so a later global TUI can
  render running state without reintroducing terminal-bottom ANSI ownership.
- Keep Rich for completed transcript output after prompt-toolkit ownership has
  ended.
- Introduce an explicit UI state model that can later move into a full
  prompt-toolkit `Application`.
- Remove `_TerminalBottomStatus` and the competing ANSI scroll-region footer
  path from the current terminal loop.
- Add PTY-level tests for prompt-at-bottom behavior because unit tests cannot
  prove terminal cursor semantics.

**Non-Goals:**

- Do not build the full-screen Application in this change.
- Do not keep the experimental `prompt_async` running-turn lifecycle in this
  change; it is deferred to the follow-up global TUI proposal.
- Do not redesign footer content, status segment labels, or theme colors beyond
  what is needed to move ownership.
- Do not change model request semantics, slash command syntax, local command
  syntax, AskUserQuestion semantics, Enter, Ctrl+J, Ctrl+D, or Esc behavior.
- Do not add a new terminal UI dependency.

## Decisions

1. Introduce an `InteractivePromptSession` boundary.

   Deepy should stop scattering raw `PromptSession.prompt()` calls and footer
   construction across `terminal.py`. A Deepy-owned wrapper can expose:

   - `prompt_next()` for idle input
   - `attach_runtime(delegate)` / `detach_runtime(delegate)` for running turns
   - `invalidate()` for status refreshes
   - one bottom-toolbar renderer for idle and running states

   This mirrors Kimi's `CustomPromptSession` shape without copying its full
   feature set.

2. Preserve running UI state as prompt message delegates.

   A runtime delegate should provide renderable fragments for:

   - realtime status line
   - compact live progress blocks such as thinking/tool/local-command activity
   - optional queued/steer/interrupt hints in a later iteration

   The prompt session boundary can render these fragments in a future runtime
   lifecycle. This change keeps the delegate contract and invalidation path, but
   does not keep the experimental turn execution wrapper that made
   `prompt_async()` active during model/local-command work.

   Alternative considered: keep `_TerminalBottomStatus` and improve cursor
   sequencing. Rejected because the bug comes from renderer ownership overlap,
   not only sequence ordering.

   A later global TUI proposal should render this delegate through a single
   long-lived prompt-toolkit `Application` instead of a one-shot writer into
   normal scrollback.

3. Keep transcript output in Rich.

   Rich prints submitted user echo, thinking/tool output, final assistant
   output, and usage footer as normal transcript output. This remains the stable
   output path until the follow-up global TUI has a dedicated transcript pane.

4. Remove `_TerminalBottomStatus`.

   The ANSI scroll-region helper caused ownership conflicts at the terminal
   bottom. Removing it avoids the known overlap and scrollback pollution class
   while runtime status display is deferred to a safer global TUI architecture.

5. Use PTY integration tests as acceptance gates.

   Fake TTY buffers are useful for formatting, but they cannot reproduce the
   cursor/save/restore interactions that caused this issue. The acceptance suite
   should include Unix PTY tests with small terminal height and long multiline
   input reaching the bottom.

## Risks / Trade-offs

- [Risk] Refactoring the prompt loop could affect slash commands, local
  commands, and clarification prompts. -> Mitigation: migrate one runtime path
  at a time and keep behavior tests around existing command flows.
- [Risk] Removing the ANSI runtime footer temporarily reduces live runtime
  status visibility. -> Mitigation: keep transcript output stable and move
  runtime status display into the follow-up global TUI proposal.
- [Risk] Prompt-toolkit invalidation could flicker under high-frequency stream
  deltas. -> Mitigation: throttle invalidation and keep final transcript output
  outside the live prompt frame.
- [Risk] PTY tests may be platform-sensitive. -> Mitigation: gate Unix PTY tests
  appropriately and keep deterministic scripted model/local-command fixtures.

## Migration Plan

1. Add the prompt session wrapper and keep behavior identical in idle mode.
2. Add a runtime delegate model that can represent model/local-command progress
   without drawing directly into terminal-bottom rows.
3. Remove `_TerminalBottomStatus` and its ANSI scroll-region tests.
4. Keep completed transcript flushing in Rich.
5. Use the resulting UI state model as the foundation for a future full-screen
   prompt-toolkit `Application`.

## Open Questions

- Should streaming assistant text be shown inside the prompt-toolkit live area
  before completion, or should only progress/status be live while final text is
  flushed after the turn?
- Should Deepy support steer/queue input during running turns in this change,
  or keep that as a later enhancement after the ownership model is stable?
- What is the minimum PTY test matrix that catches the bottom-row regressions
  without making CI flaky?
