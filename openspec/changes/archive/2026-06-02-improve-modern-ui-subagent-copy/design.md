## Context

Modern UI renders tool activity through `ToolBlock` in
`src/deepy/tui/widgets.py`. Regular tool output is intentionally compact:
parameters and output are hidden by default, with dedicated visible surfaces only
for specific cases such as todos, local commands, and diffs. Subagent calls use
the same compact path, so a successful subagent can collapse to only
`Subagent <name> ok` even though the subagent returned a useful report.

Modern UI currently defaults `TEXTUAL_DISABLE_KITTY_KEY` to `1` before importing
Textual, which protects Ghostty CJK input while still allowing a user-supplied
environment override. Copy behavior is currently based on terminal-native
selection, and tests assert that `Ctrl+C` and `super+c` are not bound by the app.
That is too narrow for macOS users who expect `Cmd+C`, while `Ctrl+C` is no
longer the advertised interrupt shortcut.

## Goals / Non-Goals

**Goals:**

- Make subagent reports inspectable in Modern UI without requiring the main
  assistant to repeat the report.
- Keep subagent transcript entries compact by default.
- Preserve the existing compact/hidden behavior for non-subagent tool output.
- Add app-level `Ctrl+C` and `Cmd+C`/`super+c` bindings for copying transcript
  content when Textual receives those key events.
- Keep Kitty keyboard protocol disabled by default and continue honoring an
  explicit environment override.

**Non-Goals:**

- Do not change shell foreground concurrency, background task behavior, or
  `ToolRuntime.cwd` semantics.
- Do not redesign all tool detail expansion.
- Do not change Classic UI rendering or copy behavior.
- Do not guarantee that every terminal delivers `Cmd+C` to Textual when Kitty
  keyboard protocol is disabled.

## Decisions

- Add a subagent-specific expansion path on the existing `ToolBlock` instead of
  introducing a separate widget class.

  Alternative considered: create a `SubagentBlock` widget. That would make the
  rendering boundary explicit, but it would require more event routing and
  history-restore changes. The smaller `ToolBlock` specialization matches the
  current tool block lifecycle and keeps the change focused.

- Keep non-subagent tool details hidden after expand.

  Modern UI already has a compact transcript contract for regular tools. This
  change only fixes the subagent visibility gap; surfacing every tool output
  would reintroduce transcript noise and conflict with the existing design.

- Show subagent parameters as a compact visible section and keep the report in
  expandable details.

  Classic UI prints a `Subagent Parameters` panel when a subagent starts. Modern
  UI should mirror the information without adding a heavy bordered panel: render
  a small subagent-only parameters section under the status line, using the
  existing compact transcript style and muted/accent color treatment. The
  expanded detail body should focus on the final subagent report and preserve
  useful file paths and command snippets, but truncate long reports to keep the
  transcript readable. Running progress can remain a short status update and
  does not need to stream nested raw output into the block.

- Register `Ctrl+C` and `super+c` on the Modern UI app as copy shortcuts.

  The binding should copy the currently focused transcript block using
  `App.copy_to_clipboard(text)`. If no transcript block is focused, the app should
  use a clear fallback such as the latest transcript block or a concise status
  message; implementation should avoid stealing prompt editing behavior more than
  necessary. `super+c` is best-effort because terminals may not deliver Cmd
  modified keys without enhanced keyboard protocol.

- Keep Kitty keyboard protocol default behavior unchanged.

  `TEXTUAL_DISABLE_KITTY_KEY` should remain set by default before Textual import,
  and user-provided overrides should still be preserved. This keeps the existing
  Ghostty CJK fix intact while adding copy bindings on top.

## Risks / Trade-offs

- `Cmd+C` may not reach Textual when Kitty keyboard protocol is disabled.
  Mitigation: register `super+c` anyway, document it as delivered only when the
  terminal sends the key event, and keep `Ctrl+C` as the reliable app-level
  binding.
- `Ctrl+C` can conflict with text-area copy expectations.
  Mitigation: route the action through transcript block focus where possible and
  update status instead of interrupting; keep `Esc` as the explicit interrupt
  shortcut.
- Subagent reports can be long.
  Mitigation: render only a bounded report body in the expanded block and keep
  the collapsed state one line.
- Generic tool details remain hidden even though `space` toggles focus state.
  Mitigation: keep that behavior intentional and test that only subagent blocks
  expose details.
