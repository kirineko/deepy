## 1. Runtime Status Rendering

- [x] 1.1 Replace the fixed terminal-bottom runtime status renderer with a normal output-flow transient renderer for model turns.
- [x] 1.2 Apply the same normal output-flow runtime status renderer to local `!cmd` command execution.
- [x] 1.3 Preserve existing runtime status visible text and truncation priorities for model, tool, thinking, and local-command details.
- [x] 1.4 Keep runtime status refreshes serialized with reasoning, tool summaries, shell output, diffs, and final answer rendering.

## 2. Bottom Overlay Removal

- [x] 2.1 Remove terminal scroll-region setup, fixed bottom-row writes, and bottom-row clearing from the runtime status path.
- [x] 2.2 Remove runtime-status-specific `anchor_status_output` and `anchor_status_output_lines` parameters and call sites.
- [x] 2.3 Remove submitted prompt bottom-row anchor checks that only protected the fixed runtime status row.
- [x] 2.4 Remove AskUserQuestion continuation anchoring that only protected the fixed runtime status row.
- [x] 2.5 Remove POSIX and Windows cursor-row probing/fallback helpers used only for runtime status anchoring.
- [x] 2.6 Preserve Esc interruption watchers and unrelated Windows/POSIX shell runtime behavior.

## 3. Styling And UI Demo

- [x] 3.1 Replace the runtime status full-line background style with segment-level foreground Rich styling.
- [x] 3.2 Style spinner, elapsed time, separators, interrupt hint, detail labels, and payload as distinct semantic segments.
- [x] 3.3 Ensure runtime status styling remains readable in dark and light terminal palettes without using a full-line background color.
- [x] 3.4 Update README, docs, or website UI demonstrations if they show or describe the old fixed-bottom runtime status behavior.

## 4. Tests And Validation

- [x] 4.1 Update terminal UI tests to assert runtime status does not set scroll regions or write to a fixed bottom row.
- [x] 4.2 Update tests that currently protect multiline prompt, AskUserQuestion, POSIX, or Windows bottom-row anchoring behavior.
- [x] 4.3 Add or update tests that verify runtime status visible text stays unchanged while style segmentation changes.
- [x] 4.4 Add or update tests that verify local command runtime status uses the same output-flow behavior.
- [x] 4.5 Run focused terminal UI tests and OpenSpec validation for this change.
