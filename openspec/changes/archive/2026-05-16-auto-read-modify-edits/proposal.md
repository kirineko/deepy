## Why

Agents sometimes call `modify` on an existing file before explicitly calling
`read`, which currently produces a visible failed tool result and forces an
extra read-then-modify round trip. This slows common edit workflows and makes
the terminal experience look worse even when the intended exact replacement is
safe to evaluate from the current file contents.

## What Changes

- Allow `modify` with `old_string`/`new_string` on an existing file to internally
  establish a managed read snapshot when the file has not been read in the
  current tool runtime.
- Keep stale-write protection unchanged for files that already have a managed
  snapshot and then change before modification.
- Keep `modify(content=...)` restricted to new files; existing-file full-content
  writes must still use the managed read/write flow.
- Preserve snippet-scoped edits and existing repeated-match safeguards.
- Return successful modify metadata that can identify when the operation used an
  internal auto-read snapshot, without rendering a separate failed tool result.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tools`: refine read-before-write behavior so exact existing-file modify
  operations may create the required managed snapshot internally while
  preserving stale-write and full-overwrite protections.

## Impact

- Affected code: `src/deepy/tools/file_state.py`,
  `src/deepy/tools/builtin.py`, `src/deepy/tools/agents.py`, and model-facing
  tool documentation under `src/deepy/data/tools/`.
- Affected specs: `openspec/specs/tools/spec.md`.
- Affected tests: focused tool runtime tests for modify/read-before-write,
  stale edit rejection, snippet behavior, metadata, and tool descriptions.
- No external dependencies or public CLI command changes are expected.
