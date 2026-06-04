## Context

The stable terminal UI clears the prompt-toolkit echo, prints a transcript copy
of submitted user input, then starts a one-line runtime status overlay for model
or local-command work. When the submitted prompt reaches the terminal's final
visible row, Deepy must create one extra scrollable row before reserving the
runtime status row so transcript output does not visually collide with the
bottom status.

The current bottom-anchor decision uses `_terminal_cursor_row()`, which is
POSIX-only: it requires `termios`, `tty`, `/dev/tty`, and an ANSI cursor
position report. On Windows these pieces are unavailable, so the cursor row is
treated as unknown and the Windows stable UI skips the anchor-scroll branch.

## Goals / Non-Goals

**Goals:**

- Detect stable UI bottom-row prompt submission on Windows.
- Preserve the existing POSIX cursor-report path and macOS behavior.
- Keep runtime status as a single fixed bottom row during active work.
- Avoid extra visible gaps when the submitted prompt is not near the terminal
  bottom.
- Cover the Windows decision path with unit tests that can run on non-Windows
  CI through fakes.

**Non-Goals:**

- Do not change experimental Textual TUI scrolling behavior.
- Do not reintroduce the old fixed two-line status/footer overlay.
- Do not change prompt keybindings, local command execution, model execution,
  session persistence, or output rendering styles.
- Do not add a third-party Windows console dependency.

## Decisions

### Use a platform-specific cursor row provider behind the existing decision

Keep `_submitted_prompt_needs_status_anchor()` as the policy function: it should
still return true only when a non-empty prompt was submitted from the terminal's
bottom row. Replace the POSIX-only assumption inside cursor probing with a small
platform split:

- POSIX terminals continue to use the current ANSI cursor report path.
- Windows terminals use a Win32 console buffer query to read the current cursor
  row relative to the visible window.
- Unknown platforms or unreadable terminals return `None`.

Alternative considered: always anchor-scroll on Windows TTYs. That would be
simple and robust against cursor-query failures, but it may add a visible blank
row even when the prompt is not at the bottom. Prefer accurate detection first.

### Use the Windows console API through the standard library

Use `ctypes` with `GetStdHandle(STD_OUTPUT_HANDLE)` and
`GetConsoleScreenBufferInfo` to read the cursor position and visible window
bounds. This keeps the implementation dependency-free and works in normal
Windows console hosts, including Windows Terminal backed by ConPTY.

The value returned to the anchor decision should be a visible 1-based row, not
the absolute screen-buffer Y coordinate. That keeps it compatible with the
existing comparison against terminal height.

Alternative considered: enable VT input and request `ESC[6n` on Windows. That
is more fragile because it depends on console modes and input handling, and it
would make the Windows path more similar to the POSIX path without solving the
lack of `/dev/tty`.

### Keep a conservative fallback explicit

If Windows cursor position cannot be read, Deepy should avoid crashing and
continue to render the runtime status. A conservative fallback may anchor-scroll
when Windows reports a TTY and the submitted prompt spans more than one rendered
row, but it should be isolated so future manual testing can adjust the behavior
without changing the POSIX path.

Alternative considered: keep returning `None` with no fallback. That preserves
the current implementation but also preserves the observed Windows regression.

## Risks / Trade-offs

- [Risk] Some Windows terminals or redirected environments may not expose a
  classic console buffer handle. -> Mitigation: return `None` or use the
  isolated fallback; never fail the turn because cursor probing failed.
- [Risk] Buffer coordinates and visible-window coordinates can be confused. ->
  Mitigation: test cursor row conversion separately with fake
  `CONSOLE_SCREEN_BUFFER_INFO` values.
- [Risk] Always anchoring as a fallback can add one extra blank line. ->
  Mitigation: prefer Win32 cursor detection and keep fallback narrow.
- [Risk] Terminal-bottom behavior is hard to validate on macOS-only machines. ->
  Mitigation: add unit tests for policy and Windows provider behavior, then rely
  on manual Windows Terminal validation before release.
