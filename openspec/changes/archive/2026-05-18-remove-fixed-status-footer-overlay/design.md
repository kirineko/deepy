## Context

Deepy 0.2.3 introduced `StatusFooter` to make the prompt footer compact and
structured. The same release also added a TTY-only runtime overlay that reserves
two terminal-bottom rows through manual ANSI scroll-region control while model
turns or local commands are running.

The structured footer is useful and should remain. The full two-row overlay is
the problem: fixing the prompt footer during active output duplicates
information that belongs to the input phase. The runtime status row itself gives
good live feedback and avoids Rich Live status interfering with realtime
Thinking output.

## Goals / Non-Goals

**Goals:**

- Remove fixed prompt-footer row reservation during model and local-command
  execution.
- Keep one fixed terminal-bottom runtime status row while work is active.
- Clear the runtime status row once work completes.
- Preserve the structured prompt footer and current footer text.
- Preserve immediate realtime thinking transcript output.

**Non-Goals:**

- Do not revert the 0.2.3 prompt toolbar wording.
- Do not remove `StatusFooter` or its prompt-toolkit/Rich formatting helpers.
- Do not change model execution, local command execution, session persistence,
  MCP behavior, or token accounting.
- Do not render the structured prompt footer in the runtime overlay.

## Decisions

### Keep a single runtime bottom status row

Model turns and local commands should use a single-row terminal-bottom status
overlay during active work. This keeps the 0.2.3 live status affordance without
pinning the structured prompt footer to a second row.

Alternative considered: use Rich `console.status(...)`. That made realtime
Thinking deltas visually break apart because Rich Live status and transcript
printing share the same output surface.

When active work resumes immediately after a terminal prompt that may have left
the cursor on the last row, such as AskUserQuestion, the status row startup must
scroll the transcript region twice, then move the transcript cursor into the
scrollable region with one spare row above the status row. For ordinary prompt
submissions it should preserve the existing cursor position so normal
conversations do not create large blank gaps before Thinking output.

### Keep prompt footer outside runtime overlay

The prompt footer should remain available when prompt-toolkit is collecting
input. During active execution, Deepy should show only the active runtime status;
it should not redraw the full prompt footer in a fixed terminal-bottom row.

Alternative considered: render the structured footer inside Rich status text.
That would make the runtime status noisy and would duplicate information already
shown at the prompt boundary.

### Keep concise active status text

Runtime status should continue to show elapsed time, interruption hint, spinner,
and the current active phase such as `thinking`, `tool ...`, or `local command`.
Thinking transcript text must remain realtime normal transcript output, not
status text.

Alternative considered: restore 0.2.2 thinking summaries in status text. That is
outside this change; the current immediate thinking transcript behavior is
better aligned with preserving full model reasoning output.

## Risks / Trade-offs

- Manual terminal-bottom rendering can be terminal-sensitive → keep the overlay
  limited to one row and clear it after active work.
- Users no longer see the static prompt footer during long active work → keep
  concise runtime status and restore the prompt footer at the next input prompt.
- Realtime Thinking output can regress if routed through Rich Live status →
  keep runtime status separate from normal transcript printing.
