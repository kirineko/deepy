## Context

The stable terminal UI currently renders some runtime detail output with Rich
`Panel` containers. Shell output and todo updates are high-frequency transcript
items, so full boxes make command-heavy turns feel visually dense. The
experimental Textual TUI already uses a lighter left-rail transcript block
language, which is a better fit for repeated tool output.

The welcome screen is also a Rich panel, but its current internal layout is
narrow and tall. It already carries the required startup information; the
problem is presentation density rather than missing data.

## Goals / Non-Goals

**Goals:**

- Make Shell output and todo updates full-width, lightweight, and visually tied
  to their status line.
- Keep command output readable without repeating the tool label in a second
  panel title.
- Make the welcome panel a wider, lower startup strip while preserving required
  startup information.
- Keep live output and replayed history rendering consistent.

**Non-Goals:**

- No changes to tool schemas or tool execution behavior.
- No changes to diff preview semantics.
- No Textual TUI redesign in this change.
- No changes to runtime status line content.

## Decisions

1. **Use left-rail blocks for Shell and todo detail output.**

   Shell and todo detail renderers will return lightweight full-width text
   blocks with a colored left rail. This preserves grouping without the visual
   weight of a titled four-sided panel. The status line remains the canonical
   place for the tool label and success/failure state.

2. **Thread width through both live and history rendering paths.**

   `render_shell_output_block()` will accept the same optional width used by
   todo and diff rendering. `render_tool_output()` and live stream rendering
   will pass the active console width so replayed session history matches live
   output.

3. **Keep todo compact and status-oriented.**

   Todo output will show progress and current task at the top, then one line
   per task with stable markers. It will not include model, context, elapsed
   time, or runtime footer details.

4. **Rework welcome content into a balanced wide panel.**

   The welcome panel will expand to terminal width while keeping enough vertical
   space for readability. The top region contains the Deepy logo and restored
   product description. The lower region restores `Session` and `Commands`
   headings, with session metadata on the left and six common commands on the
   right. Commands render one per line with consistent label-and-description
   styling.

## Risks / Trade-offs

- **Risk:** Lightweight blocks may be less visually separated than panels.
  **Mitigation:** Keep a colored rail and indentation, and preserve the status
  line above each block.
- **Risk:** Wide welcome output can wrap poorly in narrow terminals.
  **Mitigation:** Continue using Rich tables/text wrapping and add focused width
  tests for representative terminal sizes.
- **Risk:** History rendering diverges from live output.
  **Mitigation:** Route both paths through the same render helpers and add
  focused tests around `render_tool_output(..., width=...)`.
