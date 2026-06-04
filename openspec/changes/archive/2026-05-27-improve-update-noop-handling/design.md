## Design

### No-op Classification

`Update` should distinguish no-op edits from blocking validation failures:

- `old == new` is a skipped no-op edit.
- An edit that becomes no-op only because earlier staged edits already made the
  requested final state is also a skipped no-op when the file has otherwise
  changed in the current staged plan.
- A call where every edit is no-op returns `ok=true` with `noOp=true`,
  `changedFileCount=0`, `operations=[]`, and `skippedEdits`.

### Atomicity

Non-no-op failures still reject the whole batch before writing. This preserves
the preflight guarantee for stale snapshots, missing matches, ambiguous matches,
expected count mismatches, unsupported targets, path policy failures, and
guardrails.

Mixed no-op success writes only files whose staged content changed. Skipped
no-op edits are reported but are not included in committed edit indices.

### Metadata

Successful mixed results include:

- `editCount`: all requested edits
- `appliedEditCount`: edits that changed staged content
- `skippedEditCount`: skipped no-op edits
- `skippedEdits`: entries with `index`, `path`, `error`, and `error_code=no_op`

All-no-op results include the same skipped metadata plus `noOp=true`.

### Display

Tool progress summaries should use the first structured failure when available,
for example:

`Update 3 edits, 1 file  failed - edit #2 no_op: Update would not change file content.`

This keeps the concise status line useful without requiring users or models to
inspect raw JSON metadata.
