# Hide Update Audit Summary

## Why

Classic terminal audit prompts for `Update` can show a structured `summary` block
with raw `old` and `new` argument content when the update lacks enough context to
render a diff. In normal audit mode this makes the approval prompt noisy and
duplicates information that should stay focused on the target file and edit
count.

## What Changes

- Stop showing the `summary` metadata row for stable terminal `Update` audit
  approval prompts.
- Keep the concise `path` target and `edits` count visible.
- Preserve existing fallback behavior for other approval types.

## Impact

- Affects classic/stable terminal audit prompt rendering for `Update`.
- Uses the shared approval view, so Textual `Update` approvals inherit the same
  concise metadata if they render the typed summary path.
