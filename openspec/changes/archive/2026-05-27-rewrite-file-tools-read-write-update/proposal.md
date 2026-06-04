## Why

Deepy's current model-facing file tools split common file mutation work across
`read_file`, `edit_text`, `write_file`, and structured `apply_patch`, which
forces the model to choose between overlapping edit paths and provide verbose
nullable arguments. Recent real usage shows that this complexity increases
thinking length, blocks otherwise valid edits behind stale multi-file patch
preflight failures, and creates avoidable schema mistakes such as wrong patch
field names.

This release already contains a breaking session/history storage change, so the
file tool surface can be simplified in the same compatibility window instead of
preserving legacy JSON/session tool compatibility.

## What Changes

- **BREAKING** Replace the default model-facing file write surface with exactly
  three file tools: `Read`, `Write`, and `Update`.
- **BREAKING** Stop registering `read_file`, `edit_text`, `write_file`, and
  `apply_patch` as model-facing built-in tools for new runs.
- **BREAKING** Drop execution and transcript compatibility guarantees for old
  file-tool calls in old session/history records.
- Add batch/concurrent file reads through `Read`, so the model can read multiple
  files or file ranges in one tool call instead of serial turns.
- Add a unified `Update` tool for exact text replacements that supports one edit,
  multiple edits in one file, and multiple edits across files in one call.
- Keep existing safety primitives internally where useful: path policy, text
  target classification, encoding and line-ending preservation, stale write
  protection, atomic writes, diffs, and mutation metadata.
- Hide freshness tokens from the model-facing write/update contract. `Write` and
  `Update` express user intent; the runtime enforces whether the target has been
  read or must be re-read before mutation.
- Update stable terminal and experimental TUI rendering to treat `Read`, `Write`,
  and `Update` as the canonical file-tool labels and diff surfaces.
- Update prompts and tool documentation so the model is steered toward active,
  short tool calls rather than long pre-call reasoning about patch schemas.

## Capabilities

### New Capabilities
- `file-tools-v3`: Breaking v3 file tool surface for `Read`, `Write`, and
  `Update`, including batch reads, multi-edit updates, mutation safety, and
  model-facing schema constraints.

### Modified Capabilities
- `tools`: Replace the v2 file tool contract and remove structured
  `apply_patch` as the primary editing tool.
- `structured-apply-patch`: Retire the model-facing structured apply-patch
  protocol from the canonical tool surface.
- `terminal-ui`: Change file-tool rendering, malformed-argument summaries, and
  diff previews from old file-tool names to the v3 labels.
- `experimental-textual-tui`: Change retryable/malformed file-tool rendering and
  recovered-attempt folding to the v3 labels.
- `subagents`: Update allowed built-in subagent tool names to the v3 file tools.
- `deepseek-provider`: Keep cache-prefix snapshots deterministic after the tool
  surface changes and treat the new tool definitions as the canonical stable
  prefix.
- `session-context`: Treat old file-tool calls in pre-v3 histories as
  unsupported after the paired breaking session/history release.

## Impact

- Tool registration and schemas in `src/deepy/tools/agents.py`.
- File mutation runtime in `src/deepy/tools/builtin.py` and `src/deepy/tools/file_state.py`.
- Tool docs under `src/deepy/data/tools/` and system prompt guidance under
  `src/deepy/prompts/`.
- Stable terminal rendering in `src/deepy/ui/message_view.py` and
  `src/deepy/ui/terminal.py`.
- Experimental TUI rendering and diff handling in `src/deepy/tui/`.
- Subagent tool allowlists and tests in `src/deepy/subagents.py`.
- Cache-prefix and compaction behavior in `src/deepy/llm/cache_context.py` and
  `src/deepy/llm/compaction.py`.
- Existing file-tool tests, prompt tests, terminal/TUI tests, subagent tests,
  cache-context tests, and OpenSpec canonical specs.
