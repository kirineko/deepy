## Why

Deepy's current file mutation tools have useful safety checks, but the model-facing
contract still relies too much on broad `modify` guidance and runtime error recovery.
File editing should become more explicit, more patch-oriented, and safer under
Windows encoding and concurrent-change edge cases.

## What Changes

- Define the v2 model-facing file tool surface as `read_file`, `edit_text`,
  `write_file`, and `apply_patch`.
- Make `edit_text` the preferred path for small single-file exact edits and
  `apply_patch` the model-facing editing tool for multi-file and structured file
  mutations, including create, update, delete, and move operations.
- Make `edit_text` the small-scope exact/string edit path, including recoverable
  partial-read and snippet-scope mistakes, and remove the old model-facing
  `modify` alias.
- Make `write_file` the explicit new-file and whole-file replacement path, with
  stricter safety checks for replacing existing files.
- Split file mutation behavior into clearer runtime contracts: path resolution,
  read/snapshot state, text encoding, patch matching, diff generation, atomic
  writing, backups, approval/guardrail hooks, and structured tool errors.
- Strengthen existing-file safety with explicit stale-read and pre-write checks,
  including a final check immediately before a side effect is committed.
- Preserve Windows compatibility by keeping new managed text files UTF-8 without BOM
  by default while preserving existing file encodings and line endings on edit.
- Align the tool surface with OpenAI Agents SDK tool semantics, including strict
  schemas where practical, tool-local validation, and future approval/guardrail
  integration points for side-effecting tools.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tools`: Redefines the built-in file mutation contract around
  `read_file`/`edit_text`/`write_file`/`apply_patch`, makes `edit_text` the
  preferred small exact-edit tool and `apply_patch` the complex/multi-file tool,
  removes old `read`/`modify` from the model tool surface, and gives file
  mutations explicit safety, encoding, diff, approval-hook, and structured-error
  requirements.

## Impact

- Affected code: `src/deepy/tools/agents.py`, `src/deepy/tools/builtin.py`,
  `src/deepy/tools/file_state.py`, `src/deepy/tools/result.py`,
  `src/deepy/data/tools/*.md`, and tool rendering/diff surfaces.
- Affected tests: `tests/test_tools.py`, tool fixture schema tests, Windows encoding
  regression tests, stale-write tests, and any prompt/tool documentation tests.
- Runtime considerations: file writes must continue to work on macOS, Linux, and
  Windows PowerShell 7, with explicit preservation of existing encodings and line
  endings.
- Compatibility: this is an internal model tool surface migration; old
  `read`/`modify` model-facing aliases are intentionally not preserved because
  exposing both generations makes LLM tool selection worse.
