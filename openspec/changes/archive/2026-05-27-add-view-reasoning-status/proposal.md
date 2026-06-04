## Why

Deepy's live reasoning output is useful for debugging but noisy for normal use, and the current runtime status can look stalled when reasoning pauses before final output begins. Users need a concise default view that hides reasoning text while still showing visible model activity during a turn.

## What Changes

- Add a persistent UI view mode with a unified default of concise for all users.
- Add `/view` and `/view toggle` plus direct `/view concise` and `/view full` command forms.
- In concise view, hide live reasoning transcript text while preserving model reasoning behavior and session data.
- In full view, show live reasoning transcript text using the existing thinking block rendering.
- Show a concise confirmation after `/view` changes, including whether reasoning is hidden or shown.
- Change runtime model-turn status to include a per-turn cumulative stream token estimate formatted as `↓ N tokens`.
- Continue the runtime stream token estimate across reasoning and assistant output deltas in the same turn so the status does not appear frozen between phases.
- Keep `/compact` reserved for context compaction and `/model thinking` reserved for model reasoning strength.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `configuration`: add persistent UI view mode configuration and default behavior.
- `terminal-ui`: add `/view` command behavior, concise/full reasoning display, and cumulative runtime stream token status.
- `experimental-textual-tui`: mirror view mode and runtime stream token semantics in the Textual TUI.

## Impact

- Config loading and saving for `[ui].view_mode`.
- Stable terminal slash command discovery, help text, command handling, runtime status rendering, and reasoning rendering.
- Textual TUI command discovery, view-mode command handling, reasoning block rendering, and live status rendering.
- Focused tests for config defaults/persistence, terminal renderer behavior, slash command handling, status text, and Textual TUI parity.
