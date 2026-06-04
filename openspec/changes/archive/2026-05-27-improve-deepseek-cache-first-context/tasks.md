## 1. Spike And Boundaries

- [x] 1.1 Add a test-only diagnostic boundary that captures Deepy's canonical prefix snapshot and the SDK request shape without API keys or headers.
- [x] 1.2 Verify which components affect the DeepSeek cache prefix: system instructions, tool schema order, MCP tools, model id, reasoning settings, skill/rule blocks, and runtime context.
- [x] 1.3 Add an optional live DeepSeek cache probe gated by `DEEPSEEK_API_KEY` that compares append-only reuse against a deliberate mid-history mutation.
- [x] 1.4 Document that live probes must not persist API keys, request headers, or full provider payloads.

## 2. Prefix Snapshot And Session Metadata

- [x] 2.1 Add a cache-prefix snapshot type with deterministic serialization and fingerprinting.
- [x] 2.2 Integrate prefix snapshot creation into the shared runner/provider construction path.
- [x] 2.3 Persist prefix fingerprint, prefix generation, last cache-break reason, and cache usage aggregates in SQLite session metadata.
- [x] 2.4 Add migration/default behavior so existing sessions load with unknown cache state instead of failing.

## 3. Append-Only Context Semantics

- [x] 3.1 Ensure normal user, assistant, reasoning, tool call, and tool result items are appended without rewriting prior active items.
- [x] 3.2 Mark retry rollback, interrupt cleanup, `/new`, MCP tool-set changes, skill/rule/context changes, and compaction rewrites as explicit cache breaks.
- [x] 3.3 Update resume/history loading so cache metadata is restored and stale prefix metadata is invalidated when the active prefix changes.
- [x] 3.4 Add focused tests for append-only turns, cache-break reasons, and prefix generation changes.

## 4. Cache-Aligned Compaction

- [x] 4.1 Refactor compaction/folding to receive the current prefix snapshot and provider settings.
- [x] 4.2 Use the active conversation model and model settings for DeepSeek summary/fold calls.
- [x] 4.3 Preserve stable prefix and ordered tools for summary/fold requests where the SDK permits it, and append summarization instructions after the source content.
- [x] 4.4 Record the active-history replacement performed by compaction as a cache break with a concise reason.
- [x] 4.5 Add tests for active-model settings, source content preservation, and cache-break metadata.

## 5. Usage And UI Surfaces

- [x] 5.1 Aggregate normalized `prompt_cache_hit_tokens` and `prompt_cache_miss_tokens` into per-session cache statistics.
- [x] 5.2 Update `/status`, usage summaries, and session/history listings to show cache hit ratio, prefix generation, and last cache-break reason when known.
- [x] 5.3 Update the default terminal status/footer surfaces to display cache health without leaking secrets or excessive detail.
- [x] 5.4 Update the experimental Textual TUI state and widgets to display equivalent cache health and cache-break information.

## 6. Validation

- [x] 6.1 Run `openspec validate improve-deepseek-cache-first-context --type change --strict`.
- [x] 6.2 Run focused tests covering provider settings, session context, compaction, usage aggregation, terminal UI, and Textual TUI.
- [x] 6.3 Run `uv run ruff check src tests`, `uv run ty check src`, and `uv run pytest` before archive.
- [x] 6.4 Archive only after implementation and validation are complete.
