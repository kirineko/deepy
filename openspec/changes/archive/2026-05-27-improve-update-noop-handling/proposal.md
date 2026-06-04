## Why

`Update` currently rejects an entire batch when any edit is a no-op. In practice,
models sometimes include one redundant edit alongside valid edits after planning
a larger patch. The current all-or-nothing no-op handling causes avoidable
failed tool calls and an extra retry even though the valid edits are safe.

The failure summary is also too generic: the tool result includes structured
failure metadata, but the visible progress line usually only says preflight
failed.

## What Changes

- Treat no-op edits as skipped edits when the same `Update` call contains other
  valid edits for the same or other files.
- Preserve blocking preflight behavior for stale targets, missing matches,
  ambiguous matches, count mismatches, unsupported targets, path policy failures,
  and guardrail failures.
- Return successful no-op metadata when all edits are no-ops, without claiming a
  content change.
- Include skipped no-op metadata in successful mixed results.
- Improve visible failure summaries so the first structured preflight failure is
  shown in the progress line.

## Impact

- A mixed no-op `Update` batch can succeed instead of forcing a retry.
- Models get clearer feedback for real preflight failures.
- Existing mutation safety guarantees remain intact for all non-no-op failures.
