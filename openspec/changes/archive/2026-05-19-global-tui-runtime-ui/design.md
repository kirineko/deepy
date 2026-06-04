## Context

The `prompt-toolkit-runtime-ui` change stabilized idle prompt/footer ownership
and removed the fragile `_TerminalBottomStatus` ANSI scroll-region path, but it
intentionally deferred live runtime display. A later experiment tried to make
model turns and local commands run inside a temporary `prompt_async` lifecycle.
Manual testing showed multiple regressions:

- runtime status appeared alongside thinking output instead of owning a stable
  runtime surface
- thinking output could disappear or be left in an incomplete state
- the next user prompt could become unusable after a turn
- bottom footer placement was still sensitive to concurrent Rich output

The root cause is that Deepy currently treats streaming events as immediate
terminal print operations. `TerminalStreamRenderer` both mutates runtime
status/progress and prints thinking/tool output through Rich. A prompt-toolkit
runtime owner cannot be stable while Rich is also writing active output into
the same terminal region.

The Kimi CLI reference points to a safer shape:

```text
CustomPromptSession
├─ prompt router task keeps exactly one prompt read alive
├─ running prompt delegate attaches while a turn runs
├─ view consumes wire/runtime events into state
├─ prompt message renders agent status + interactive body
└─ bottom_toolbar renders footer
```

Deepy should adopt that architecture incrementally. The first goal is a global
interactive shell/controller with event-driven view state, not an immediate
full-screen `Application` rewrite.

## Goals / Non-Goals

**Goals:**

- Establish one global prompt-toolkit UI owner for idle prompts and running
  model/local-command turns.
- Replace direct runtime `console.print` calls with an event-driven view model
  while the runtime UI is active.
- Keep thinking text visible and complete, including after final transcript
  commit.
- Keep tool progress, local-command status, elapsed time, interruption hints,
  and compact footer in a single coherent prompt-toolkit surface.
- Ensure subsequent prompts remain usable after a running turn completes.
- Provide explicit running input routing for cancel, queue, and ignored input.
- Keep the implementation incremental enough to validate with PTY tests after
  each phase.

**Non-Goals:**

- Do not immediately force `/model`, `/theme`, `/skills`, session picker, or
  other existing prompt-toolkit `Application` pickers into a single full-screen
  layout.
- Do not change model request semantics, session persistence, tool semantics,
  slash command syntax, or local command syntax.
- Do not add a new TUI dependency.
- Do not reintroduce ANSI scroll-region ownership for footer/status placement.
- Do not support full steer-input semantics unless queue/cancel/ignore routing
  is stable first.

## Decisions

1. Use a global interactive shell/controller before a full-screen Application.

   The next implementation should introduce a controller that owns prompt
   lifecycle, running state, input routing, and runtime view attachment. This is
   closer to Kimi's `CustomPromptSession` pattern than to a one-off
   `prompt_async` wrapper.

   Alternative considered: immediately build a full-screen `Application`.
   Rejected for the first pass because Deepy already has several isolated
   picker Applications and a large Rich transcript surface. Moving everything
   at once would make regressions hard to isolate.

2. Split runtime event handling into reducers and renderers.

   Streaming events should update a `RuntimeViewState` or equivalent view model.
   Rendering should read that state to produce prompt-toolkit formatted text or
   Rich renderables converted to ANSI/formatted text. Direct runtime
   `console.print` from `TerminalStreamRenderer` should be removed from the
   active running UI path.

   Alternative considered: keep `TerminalStreamRenderer` and throttle printing.
   Rejected because the failure was ownership overlap, not only repaint rate.

3. Commit transcript output after runtime ownership releases.

   The running view may show transient thinking/tool/progress blocks while the
   turn is active. When the turn finishes, Deepy should commit a complete
   transcript representation in a controlled step so scrollback is readable and
   complete. This avoids Rich writing into the prompt-owned active surface.

   The committed transcript does not have to look identical to the live panel.
   It should preserve user echo, complete thinking, tool summaries/output,
   final assistant output, and usage footer.

4. Keep running input routing explicit and conservative.

   During a running turn, ordinary text input should be routed deliberately:

   - Esc/Ctrl-C: interrupt the running work
   - Enter with text: queue a follow-up for after the current turn, or ignore
     with a visible hint if queueing is not implemented in the first task slice
   - Ctrl+J: newline if the running input buffer is enabled
   - Ctrl+D: preserve existing exit behavior only in idle mode

   This avoids the second-prompt corruption seen in the failed experiment.

5. Treat local commands as runtime work in the same UI model.

   Interactive `!` local commands should not be a special terminal writer. They
   should run under the same global UI owner and update the same runtime view
   model with command text, elapsed time, interrupt status, and final output
   commit.

6. Keep PTY tests as the acceptance gate.

   Unit tests can validate reducers and render fragments, but only PTY tests
   catch bottom-row ownership, prompt recovery, cursor placement, and repeated
   turns.

## Risks / Trade-offs

- [Risk] Converting Rich renderables to prompt-toolkit output may lose styling
  fidelity. -> Mitigation: start with compact live panels and keep high-fidelity
  transcript commit rendering through existing Rich utilities after runtime
  release.
- [Risk] Keeping a prompt alive while model work runs can confuse history and
  submit semantics. -> Mitigation: implement an explicit prompt router and
  running input policy with targeted tests for Enter, Ctrl+J, Ctrl+D, Esc, and
  second-turn submission.
- [Risk] A global UI controller may touch much of `terminal.py`. -> Mitigation:
  first extract reducers and transcript commit without changing user behavior,
  then swap the runtime path.
- [Risk] Runtime view and final transcript can diverge. -> Mitigation: use the
  same event-derived state for both live rendering and final commit wherever
  possible.
- [Risk] Existing picker Applications may conflict with a prompt router. ->
  Mitigation: keep modal picker flows as blocking operations for this proposal;
  integration into a single Application remains a later step.

## Migration Plan

1. C0: Extract event-driven state.
   - Add runtime view state and reducers for model events, thinking, tool calls,
     usage, local command lifecycle, and status.
   - Add a transcript commit renderer that can produce the existing visible
     output from state after a turn.
   - Keep the current prompt loop during this phase.

2. C1: Introduce global prompt shell/controller.
   - Keep one active prompt read while idle or running.
   - Attach a running view delegate while model/local-command work is active.
   - Route running input explicitly to interrupt, queue, or ignore.
   - Stop direct Rich printing during active runtime UI.

3. C2: Stabilize runtime and local-command display.
   - Render thinking, tool progress, elapsed time, interrupt hints, and footer
     through the global UI owner.
   - Commit final transcript after runtime view detaches.
   - Cover repeated turns and local commands with PTY tests.

4. C3: Optional full Application preparation.
   - Once C1/C2 are stable, decide whether to migrate pickers and transcript
     scrolling into a single full-screen `Application`.

## Open Questions

- Should queued follow-up input be included in the initial implementation, or
  should Enter during running turns be ignored with a visible hint until the UI
  owner is stable?
- Should thinking text be fully visible in the live runtime panel, or should the
  live panel show a bounded preview while the final transcript commit contains
  the complete thinking block?
- Should local command stdout/stderr stream live inside the runtime panel, or be
  summarized live and committed after the command finishes?
