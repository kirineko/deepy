## Context

The stable terminal UI currently renders runtime model and local-command status
through a fixed terminal-bottom overlay. That path uses terminal scroll regions
and explicit cursor movement to reserve the final row while active work runs.

The input phase already has a legitimate bottom owner: prompt-toolkit's
`bottom_toolbar`. The runtime overlay therefore creates a second owner for the
same screen area. Prior fixes added multiline prompt anchoring,
AskUserQuestion continuation anchoring, and POSIX/Windows cursor-row detection
to work around this collision, but those compensations increase fragility.

The desired state is narrower: only runtime status line placement and styling
change. The status wording remains unchanged.

## Goals / Non-Goals

**Goals:**

- Move runtime status rendering into the normal output flow.
- Keep the existing runtime status wording and truncation priorities.
- Remove terminal-bottom scroll-region ownership and row reservation.
- Remove submitted prompt and AskUserQuestion anchor handling that only exists
  for the fixed bottom runtime row.
- Remove POSIX and Windows cursor-row probing used only for that anchoring
  decision.
- Style runtime status lines with segment-level foreground colors and no
  full-line background color.
- Preserve prompt-toolkit bottom toolbar behavior during input.

**Non-Goals:**

- Do not change runtime status copy.
- Do not change final assistant output, thinking transcript copy, tool result
  summaries, usage footers, or slash-command output.
- Do not change Esc interruption behavior or the POSIX/Windows Esc watchers.
- Do not change Textual TUI behavior.
- Do not introduce a new terminal UI dependency.

## Decisions

### Render runtime status as an output-flow transient line

Runtime status should be printed and refreshed in normal transcript space rather
than drawn on the terminal's final row.

Rationale: normal output flow gives Rich and prompt-toolkit distinct ownership
phases. prompt-toolkit owns the bottom toolbar while reading input; Rich owns
normal output while a run is active. No scroll-region mutation is needed.

Alternative considered: keep the bottom overlay and refine anchor rules. This
preserves a persistent status-bar visual, but it keeps the root conflict and
requires terminal-specific cursor handling to avoid covering prompt/question
text.

### Remove bottom-row anchoring and cursor-row detection

The implementation should remove `anchor_status_output`,
`anchor_status_output_lines`, submitted-prompt status-anchor checks, and the
POSIX/Windows cursor-row helpers used only to decide whether to scroll content
above the bottom runtime row.

Rationale: once runtime status is not fixed to the bottom row, those code paths
no longer protect any owned region. Keeping them would preserve unnecessary
platform complexity and could continue to move output unexpectedly.

Alternative considered: keep the helpers as a fallback for narrow terminals.
This is not justified because the new renderer does not require a protected
bottom row.

### Preserve wording, refactor styling

Runtime status text construction should keep the same visible text. Styling
should move from a full-line ANSI background to Rich segment styles over the
existing semantic parts: spinner, labels, elapsed value, separators, interrupt
hint, tool/local-command label, and payload.

Rationale: foreground-only segmented styling keeps status readable in the normal
transcript without making it look like a footer or status bar. It also allows
the interrupt hint and active detail to remain discoverable without overpowering
payload text.

Alternative considered: use one muted color for the entire status line. This is
simpler, but loses the semantic separation requested for normal-flow display.

### Keep output serialization

The runtime status renderer should continue coordinating with stream output so
status refreshes do not interleave with reasoning, tool call summaries, shell
output blocks, diffs, or final answer rendering.

Rationale: moving status into normal output solves bottom ownership, but it
still needs predictable ordering with live stream events.

## Risks / Trade-offs

- Runtime status may be less visually persistent than a fixed bottom row.
  -> Use concise refresh behavior and segment-level styling so active work is
  still visible without owning the terminal bottom.
- Some terminals may render carriage-return line refresh differently.
  -> Keep tests focused on ANSI sequences that must not appear, especially
  scroll-region setup and final-row writes.
- Removing cursor-row helpers could accidentally remove unrelated Windows
  behavior.
  -> Limit removal to status-anchor cursor detection. Keep Esc interruption
  watchers and shell/runtime environment logic intact.
- Segment-level styling could accidentally alter truncation output.
  -> Continue fitting/truncating status text based on plain text width, and
  test that visible text is unchanged.

## Migration Plan

Implement as an internal terminal UI change with no user-facing command or
configuration migration.

Rollback is straightforward: restore the previous bottom overlay renderer and
its anchoring call sites if the normal-flow renderer proves unusable. The
preferred rollback checkpoint should be before removing old tests, so behavior
can be compared against the fixed-bottom contract if needed.
