## Why

Model-generated patch strings are fragile for HTML, CSS, YAML, and multi-file edits because the model must handwrite a custom diff-like DSL with exact line prefixes. Recent user traces show repeated parser failures, unclear retry paths, long multi-file waits, and incomplete multi-file diff display, so the patch protocol should move from string syntax to structured file operations before the v2 file mutation surface is released.

## What Changes

- **BREAKING**: Replace the model-facing `apply_patch` string payload with a strict-compatible structured `operations` payload.
- **BREAKING**: Remove legacy `patch` string compatibility from the model-facing tool schema because this protocol has not shipped yet.
- Define operation types for `create_file`, `replace_file`, `delete_file`, `move_file`, `replace_block`, `insert_before`, `insert_after`, and `replace_all`.
- Route every operation through the existing managed mutation engine: path policy, text encoding, snapshot and stale checks, patch matching, diff building, atomic writes, backup metadata, and guardrail hooks.
- Improve `apply_patch` pending UI so it can summarize operation count and target file names immediately without rendering large arguments.
- Improve multi-file result display so every changed file receives visible diff-preview budget while full diff metadata remains available.
- Update prompts and tool descriptions so models prefer structured `apply_patch.operations` for multi-file, multi-edit, create/delete/move, or large block changes, while keeping `edit_text` for small exact single-file edits.

## Capabilities

### New Capabilities

- `structured-apply-patch`: Defines the structured `apply_patch` operation protocol, operation semantics, validation, result metadata, and display requirements.

### Modified Capabilities

- `tools`: Replaces the existing patch-string `apply_patch` requirement with a structured operation-list contract and updates tool display expectations for operation summaries and multi-file diff previews.

## Impact

- Affected model-facing tool schema: `apply_patch`.
- Affected tool implementation: built-in file mutation tools, patch parsing/planning, shared mutation engine adapters, and Agents SDK tool registration.
- Affected prompts/docs: file tool guidance and tool descriptions.
- Affected UI/TUI: pending tool-call summaries and multi-file diff preview rendering.
- Affected tests: schema tests, prompt/tool docs fixtures, structured operation validation, path/stale/encoding regression coverage, and multi-file UI rendering tests.
