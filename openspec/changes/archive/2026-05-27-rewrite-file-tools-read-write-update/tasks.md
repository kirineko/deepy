## 1. Runtime File Tool Core

- [x] 1.1 Add v3 `Read`, `Write`, and `Update` runtime methods that reuse existing path policy, target classification, encoding, line-ending, stale-write, atomic-write, and diff helpers.
- [x] 1.2 Implement `Read` single-target and multi-target normalization, including path/range/head/tail/offset/limit forms.
- [x] 1.3 Execute independent `Read` targets concurrently and return per-target results plus aggregate metadata.
- [x] 1.4 Implement `Write` new-file creation and existing-file replacement without model-facing freshness token fields.
- [x] 1.5 Implement `Update` input normalization for single edit, per-file edit arrays, and top-level cross-file edit arrays.
- [x] 1.6 Implement `Update` staged preflight for exact match, replace-all, expected count, stale/unread target, unsupported target, path policy, no-op, and guardrail failures.
- [x] 1.7 Implement `Update` commit behavior with per-file diffs, changed-file metadata, refreshed runtime read state, and late failure or rollback metadata.

## 2. Tool Registration And Prompt Surface

- [x] 2.1 Replace model-facing file tool registration in `src/deepy/tools/agents.py` with `Read`, `Write`, and `Update`.
- [x] 2.2 Remove default registration of `read_file`, `edit_text`, `write_file`, and `apply_patch` for new main-agent runs.
- [x] 2.3 Keep or delete old runtime helpers only as private implementation details; ensure the model prompt and tool list cannot call them.
- [x] 2.4 Replace file tool documentation under `src/deepy/data/tools/` with concise v3 docs.
- [x] 2.5 Update system prompt guidance to steer the model toward `Read`, `Write`, and `Update` without mentioning v2 file tools or snapshot-token copying.
- [x] 2.6 Ensure provider schema compatibility does not reintroduce required nullable filler fields for v3 file tools.

## 3. UI, TUI, And Diff Rendering

- [x] 3.1 Update stable terminal labels, progress summaries, malformed argument summaries, and diff previews to recognize `Read`, `Write`, and `Update`.
- [x] 3.2 Update experimental TUI tool blocks, retryable argument failure states, recovered-attempt folding, and mutation diff views for v3 file tools.
- [x] 3.3 Remove new-run UI assumptions that `apply_patch` diffs are special or full-preview-only.
- [x] 3.4 Verify malformed `Write` and `Update` payloads do not dump large content, `old`, `new`, or edit arrays in collapsed transcript views.

## 4. Subagents, Cache, And Session Context

- [x] 4.1 Update built-in subagent tool allowlists to use v3 file tool names.
- [x] 4.2 Update custom subagent validation so removed v2 file tool names are rejected with concise diagnostics.
- [x] 4.3 Update DeepSeek cache-prefix snapshot tests and diagnostics for the v3 ordered built-in tool schema set.
- [x] 4.4 Verify compaction uses the same stable provider/model/tool prefix snapshot while continuing to forbid tool calls.
- [x] 4.5 Remove old file-tool execution and old transcript compatibility assumptions from session/history code paths affected by the paired breaking release.

## 5. Tests And Validation

- [x] 5.1 Replace v2 file-tool registration/schema tests with v3 registration and schema tests.
- [x] 5.2 Add focused tests for `Read` batch concurrency, per-target errors, range/head/tail metadata, and read-state recording.
- [x] 5.3 Add focused tests for `Write` creation, existing-file replacement, stale/unread rejection, encoding preservation, and line-ending preservation.
- [x] 5.4 Add focused tests for `Update` single edit, multi-edit same-file, multi-file batch, replace-all, expected-count mismatch, no-op, stale target, and rollback or late-failure metadata.
- [x] 5.5 Update prompt, terminal UI, TUI, subagent, cache-context, compaction, and session-context tests for v3 file tool names.
- [x] 5.6 Run `openspec validate rewrite-file-tools-read-write-update --type change --strict`.
- [x] 5.7 Run focused tests for tools, prompts, terminal UI, TUI, subagents, cache context, compaction, and session context.
- [x] 5.8 Run `uv run ruff check src tests`, `uv run ty check src`, and `uv run pytest` before archiving.

## 6. Archive Readiness

- [x] 6.1 Confirm canonical specs after archive will no longer expose `apply_patch` as a model-facing primary editing tool.
- [x] 6.2 Confirm old file-tool history compatibility is documented as intentionally unsupported in the breaking release window.
- [x] 6.3 Archive the change only after implementation and validation pass.
