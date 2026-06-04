## Context

Deepy currently uses prompt-toolkit for idle input, Rich for transcript output,
and a small ANSI scroll-region helper for running status/footer rows. Terminal
testing showed that trying to fix bottom-row conflicts by adding more ANSI
coordination around idle prompt input is fragile and can introduce worse
regressions such as misplaced footers, large blank areas, or hidden status
bars.

This archived change therefore keeps only the low-risk input-side fix.

## Goals / Non-Goals

**Goals:**

- Prevent a long multiline prompt buffer from growing without a visible height
  cap.
- Keep the compact prompt footer visible enough for ordinary prompt editing.
- Avoid the `PromptSession.prompt(..., erase_when_done=...)` runtime error by
  configuring cleanup at session creation.
- Keep the code change isolated to prompt input setup.

**Non-Goals:**

- Do not rework `_TerminalBottomStatus`.
- Do not introduce an idle footer overlay outside prompt-toolkit.
- Do not change local command, model streaming, tool output, thinking output,
  AskUserQuestion, slash command, Enter, Ctrl+J, Ctrl+D, or Esc behavior.
- Do not claim full bottom-area ownership is solved in this change.

## Decisions

1. Cap visible prompt input height with a prompt session subclass.

   `PromptSession` already builds the editable prompt buffer as a
   prompt-toolkit `Window`. A small Deepy subclass can override the default
   buffer-control height and set a maximum row count. This limits visual growth
   while leaving prompt-toolkit in charge of scrolling the input buffer.

2. Keep `erase_when_done` at session initialization.

   The installed prompt-toolkit API accepts `erase_when_done` on the
   `PromptSession` constructor, not on `PromptSession.prompt()`. Passing it at
   the prompt-call layer caused startup failure, so the setting belongs in
   `create_prompt_session()`.

3. Do not patch terminal bottom ownership in this change.

   Experiments with prompt footer gaps, forced pre-scroll carving, and a
   self-managed idle footer overlay showed that partial ownership fixes are more
   dangerous than useful. The architecture-level fix belongs in the follow-up
   prompt-toolkit runtime UI change.

## Risks / Trade-offs

- [Risk] Capping visible input height may not fully solve bottom collisions in
  all terminals. -> Mitigation: treat this as a narrow prompt-editing
  improvement, not the final bottom-area fix.
- [Risk] Overriding a prompt-toolkit private-ish method may be sensitive to
  future prompt-toolkit changes. -> Mitigation: keep the subclass tiny and
  covered by focused tests.
- [Risk] Users may still hit runtime/footer conflicts during model or local
  command work. -> Mitigation: address that in the prompt-toolkit-owned runtime
  UI proposal.

## Migration Plan

- No data migration is required.
- Rollback is limited to `prompt_input.py` and prompt input tests.

## Open Questions

- What maximum visible input height feels best across small and large
  terminals?
- Should the follow-up runtime UI keep Rich only for completed transcript
  output, or should it also render completed turn output through
  prompt-toolkit before flushing to scrollback?
