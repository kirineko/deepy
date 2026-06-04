# Polish Runtime Output And Write Recovery

## Why

Recent file-tool and runtime-status changes improved safety and progress
visibility, but a few visible edges still hurt agent flow:

- `Write(overwrite=true)` rejects existing files that have not been read even
  though `Update` can safely auto-read missing snapshots before mutation.
- Runtime status can show long tool argument payloads after the interrupt hint,
  causing flicker and low-value status text.
- Assistant Markdown code blocks render as lightly styled text rather than a
  distinct terminal code block.

## What Changes

- Let `Write(overwrite=true)` auto-read an existing text file when no managed
  snapshot exists, then perform the same freshness check before writing.
- Keep stale-snapshot protection for files that were previously read and then
  changed outside Deepy.
- Trim model-turn runtime status to elapsed time, cumulative stream token
  estimate when available, concise state/tool name, and `esc to interrupt`.
- Render assistant fenced code blocks as padded terminal code blocks without
  exposing raw fence syntax.

## Non-Goals

- Do not change local `!cmd` command status behavior.
- Do not remove diff previews or failure summaries.
- Do not change provider usage accounting or context-window formatting.
