## Context

Deepy renders tool output through `src/deepy/ui/message_view.py`. Both `edit`
and `write` tool results are parsed from structured tool JSON and routed through
`render_tool_diff_preview()`, but the rendering currently splits into two
visual paths:

- `edit` uses `render_diff_preview_line()`, which shows old/new line gutters,
  `+` or `-` markers, and added/removed background styles.
- `write` uses `render_write_preview_line()`, which has its own gutter/content
  palette and intentionally avoids the same diff-line presentation.

Both paths assemble Rich `Text` from a gutter segment and a content segment. Rich
only applies background color to the characters in those segments, so added and
removed backgrounds stop at the end of the code text. On short lines or test
blocks this creates fragmented green/red shapes rather than the continuous
terminal-width bands users expect from a diff preview.

The rendering also appears in both realtime stream output and session/history
rendering. Any width-aware change should therefore keep a clean path from the
active `Console` width to the diff preview renderer.

## Goals / Non-Goals

**Goals:**

- Make `write` and `edit` use one consistent diff preview visual model.
- Fill added and removed line backgrounds to the available terminal width.
- Preserve current behavior where large `write` previews can show all generated
  file lines instead of being truncated like edit previews.
- Keep dark and light theme palettes legible after background fill is extended.
- Cover the rendering with deterministic Rich text tests and stream rendering
  tests.

**Non-Goals:**

- Change tool execution semantics, tool JSON metadata, or diff generation.
- Add a new terminal rendering dependency.
- Render unchanged/context lines as colored full-width blocks.
- Force all history renderers to know a real terminal width when unavailable;
  they can fall back to existing non-width-aware behavior.

## Decisions

1. Unify write/edit preview line rendering.

   `write` should no longer have a separate content-style renderer. It should use
   the same line rendering model as `edit` so added and removed lines have the
   same gutter, marker, and background treatment. The label can still say
   `Wrote` for write results and `Edited` for edit results.

   Alternative considered: keep the write renderer and copy width fill logic
   into it. Rejected because it preserves the visual inconsistency the change is
   meant to remove.

2. Keep write truncation behavior separate from visual style.

   The existing renderer avoids line truncation for `write` results so large
   generated files can be reviewed fully. This should be preserved. Unifying
   style does not require unifying the edit preview line limit.

   Alternative considered: make write follow `MAX_DIFF_LINES` exactly like edit.
   Rejected because users explicitly want large writes to remain fully visible.

3. Pass available width into the diff preview renderer.

   Width fill belongs in the Rich rendering layer, not in diff parsing or tool
   output metadata. Realtime terminal output should pass `console.width` into
   `render_tool_diff_preview()`. Other call sites should accept an optional
   width and gracefully fall back when no width is available.

   Alternative considered: pad the stored diff text itself. Rejected because
   stored diffs should remain semantic and independent of the user's terminal
   width.

4. Fill only changed-line backgrounds.

   Added and removed lines should receive terminal-width background fill.
   Context lines should remain muted/plain so the colored bands keep their
   meaning and do not turn the entire preview into a dense block.

   Alternative considered: fill every preview line. Rejected because it reduces
   scanability and makes context visually compete with actual changes.

5. Preserve theme palette ownership.

   Dark and light mode should continue to use the existing palette roles for
   added/removed gutters and content. Width fill should extend those styles; it
   should not introduce hard-coded colors outside the palette.

   Alternative considered: create separate full-line background colors. Rejected
   unless existing contrast tests prove the current palette roles are
   insufficient.

6. Use Rich/Pygments for content token highlighting, not diff structure.

   Rich `Syntax` can render source code with token colors and it can render a
   unified diff as diff text, but it does not preserve Deepy's old/new source
   line gutters and full-width added/removed palette backgrounds by itself. The
   diff preview should therefore keep owning line numbers, `+`/`-` markers, and
   background fill, while applying Rich/Pygments token styles only to the line
   content segment.

   Alternative considered: hand the whole diff block to Rich `Syntax` using the
   `diff` lexer. Rejected because its line numbers describe the diff document,
   not the old/new source files, and it would not highlight embedded Python,
   Rust, or other programming language content inside changed lines.

## Risks / Trade-offs

- Terminal width can be smaller than gutter plus content -> do not attempt
  negative padding; rely on Rich/terminal wrapping for overlong lines.
- `Text.cell_len` and CJK/wide characters can make string length calculations
  wrong -> use Rich cell measurement behavior where available instead of raw
  `len()`.
- History rendering may not always know the original terminal width -> support
  optional width and keep a reasonable fallback.
- Full-width backgrounds can look too heavy in light mode -> add explicit
  light-theme regression tests and adjust only palette roles if needed.
- Large writes plus full-width fill produce more styled text spans -> keep the
  implementation simple and avoid per-character spans.
- Syntax themes can include their own background color -> rewrite syntax token
  spans onto the active diff palette background before appending width padding.

## Migration Plan

1. Add tests that describe the desired unified write/edit style and full-width
   changed-line fill.
2. Thread optional width through `render_tool_diff_preview()` and realtime tool
   output rendering.
3. Replace the write-specific line renderer with the shared diff-line renderer
   while preserving the existing write no-truncation path.
4. Verify dark and light theme span styles and rendered text output.
5. Run message view, terminal UI, and broader UI tests.

## Open Questions

- Should session/history replay use the current terminal width when rendering old
  tool outputs, or should width fill be limited to live stream output first?
