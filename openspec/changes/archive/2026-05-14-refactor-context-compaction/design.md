## Context

Deepy currently has three disconnected and incorrect pieces of context management:

- `RunConfig.session_input_callback` trims the list sent to the model when a threshold is exceeded.
- `DeepyJsonlSession` stores JSONL history and estimates `activeTokens` by summing stored records.
- `DeepySessionManager.compact_session()` clears the session and writes only a placeholder notice.

That means the model may see a trimmed context while the session on disk still contains all old items, manual compaction destroys useful history, and token pressure can be undercounted after large appended records. These behaviors should be removed from the main path rather than patched in place. Kimi CLI provides the replacement shape: context history is a first-class state object, model usage updates a precise token checkpoint, later appended messages add pending estimated tokens, auto compaction checks both ratio and reserved-output thresholds, and `/compact` rewrites context only after a successful summary is produced.

Deepy is built on OpenAI Agents SDK sessions, so the design must also respect the SDK boundary:

- `Session` persistence is the canonical local history.
- `session_input_callback` affects the model input for the current turn, not persisted history.
- Compaction that should survive `/resume` must rewrite the local session, not only return a filtered input list.
- The Agents SDK callback layer is not the context manager. It may prepare input, but it must not silently compact, trim, or become the source of context accounting truth.

## Goals / Non-Goals

**Goals:**

- Replace the existing compact/context implementation as a single subsystem, not as incremental fixes around the current helpers.
- Provide a safe `/compact [focus]` command for the active interactive session.
- Replace lossy placeholder compaction with model-generated summaries plus preserved recent items.
- Make auto compaction durable and observable by compacting the session before the next model turn when context pressure requires it.
- Track context pressure using precise usage when available plus pending estimated tokens for records appended after the latest usage checkpoint.
- Add reserved-output budgeting so Deepy compacts before the remaining context is too small for a useful response.
- Preserve pre-compaction history by rotating or archiving the JSONL file before rewriting the active session.
- Keep session replay compatible with OpenAI Agents SDK item shapes after compaction.

**Non-Goals:**

- Introduce a new storage backend such as SQLite.
- Implement long-term memory, searchable offloaded artifacts, or subagent context isolation in this change.
- Use provider-specific server-side Responses API compaction; Deepy currently targets an OpenAI-compatible DeepSeek provider through the Agents SDK.
- Preserve the old placeholder compaction semantics, old silent model-input trimming, or old `activeTokens` calculation behavior.
- Guarantee exact token counts before a provider returns usage; pending token counts remain estimates.

## Decisions

### 1. Replace old helpers with a context state service

Introduce a session-level context state service that owns token accounting, compaction policy, and safe session rewrite. Existing helpers such as `compact_items_for_context()` and placeholder `DeepySessionManager.compact_session()` should be removed from the implementation path. If a public method name still has callers, it may remain only as a thin entry point into the new service, with none of the old behavior retained.

The service accepts a `DeepyJsonlSession`, settings, provider bundle, trigger reason (`manual` or `auto`), and optional focus instruction.

The service will:

1. Load active SDK items.
2. Restore or compute the current context token state.
3. Decide whether compaction is required from policy.
4. Select older items to summarize and recent items to preserve.
5. Build a compaction prompt from older items plus optional user focus.
6. Run a minimal compaction model call without Deepy's normal tools.
7. Strip any analysis wrapper and persist only the final summary content.
8. Rotate/archive the original session file.
9. Rewrite the active session to contain a compaction summary item plus preserved recent items.
10. Update session index token metadata and usage metadata.

Rejected path: extending `compact_items_for_context()` to insert a better notice. That remains transient, does not fix `/resume`, and would preserve the main bug.

### 2. Preserve recent messages by policy, not by arbitrary truncation

Use a Kimi-like preservation policy:

- Preserve the most recent complete user/assistant exchange count by default.
- Also respect a token budget cap for preserved recent context.
- Keep tool-call dependency integrity so tool outputs are not retained without their corresponding call item and function calls are not retained without required outputs.

The summary item should be represented as a normal SDK-compatible message so replay works. It should explicitly say previous context was compacted and include the generated structured summary.

Alternative considered: preserve a fixed number of raw JSONL records. Rejected because records do not necessarily align with conversation turns or tool-call groups.

### 3. Add token accounting metadata to the session index

Keep `activeTokens` only as a derived display/index field, and calculate it from:

- `lastUsageTokens`: the latest precise prompt/context token count known from a model call or compaction estimate.
- `pendingTokens`: estimated tokens for records appended after the latest usage checkpoint.
- `activeTokens`: the user-facing current estimate, equal to `lastUsageTokens + pendingTokens` when checkpoint metadata is available, otherwise the existing full-record estimate.

This mirrors Kimi's `token_count_with_pending` without depending on old `activeTokens` as truth. Metadata should be stored in the session index, and optionally in internal JSONL meta records if needed for restoration after index loss.

Rejected path: always fully re-estimating all records and continuing to write the result into `activeTokens`. That misses the important bug class where the last precise API usage is below threshold but a newly appended large tool result pushes the next request over the limit.

### 4. Trigger auto compaction before model calls

Before `Runner.run_streamed`, load the target session and compute current context pressure:

```
effective_tokens = last_usage_tokens + pending_tokens
ratio_trigger = effective_tokens >= window_tokens * compact_trigger_ratio
reserved_trigger = effective_tokens + reserved_context_tokens >= window_tokens
```

When either trigger is true, run durable compaction first. If compaction succeeds, run the user turn against the compacted session. If compaction fails, surface a clear error and do not rewrite the session.

If compaction is required but cannot be completed, the turn must stop with a clear error. Deepy must not silently trim older prepared input as a substitute for compaction. The `session_input_callback` path should be limited to deterministic SDK input assembly and must not mutate, summarize, or silently drop context.

Alternative considered: compact after each turn. Rejected because it wastes model calls and can compact at poor task moments. Pre-turn compaction is predictable and handles large pending tool output before the next request.

### 5. Add reserved context configuration

Replace the compact policy surface under `[context]` with canonical fields:

- `reserved_context_tokens`, defaulting to `50_000`.
- `compact_preserve_recent_messages`, defaulting to a conservative small count.
- `compact_preserve_recent_tokens`, optional override.

`window_tokens` and `compact_trigger_ratio` remain useful as policy inputs. `compact_prompt_token_threshold` should be removed from runtime config and compaction decisions. If it still appears in an old user config file, Deepy should ignore it like any other unknown TOML key. The implementation should have one canonical trigger path, not parallel old/new threshold checks.

Alternative considered: only use ratio. Rejected because smaller context windows can run out of output budget before the ratio threshold.

### 6. Rotate history before rewriting

Compaction must not be destructive until the replacement has been generated. The rewrite flow should be:

1. Generate summary in memory.
2. Build replacement item list.
3. Move the original JSONL to a timestamped archive path.
4. Write replacement JSONL to the active path.
5. Update the index.
6. If writing replacement fails, restore the archived original.

This keeps compaction recoverable and makes failures inspectable.

### 7. Expose compaction events in terminal UI

Interactive UI should show clear but compact status:

- `/compact` with no active session: "No active session to compact."
- Empty session: "The context is empty."
- Running: "Compacting context..."
- Success: include before/after token estimates and preserved item count.
- Failure: show error and confirm the original session was left unchanged.

Auto compaction should show a short pre-turn status line so users understand why a model call starts with compaction.

## Risks / Trade-offs

- Summary can lose critical task details -> Preserve recent turns, use a structured summary prompt, and add tests for goal retention, errors, file paths, and pending tasks.
- Compaction model call can fail -> Generate before rotating, restore original on replacement failure, and surface the error without changing session history.
- Tool-call groups can become invalid after preservation -> Preserve or drop dependent tool-call groups as a unit and reuse existing replay sanitization tests.
- Token accounting can drift -> Treat precise model usage as authoritative, use pending estimates only until the next model usage update, and expose estimates as estimates in UI.
- Additional compaction calls add latency/cost -> Trigger only when policy requires it or the user explicitly invokes `/compact`.
- Existing tests assume `session_input_callback` performs compaction -> Rewrite tests so callback compaction is gone and durable compaction is the only compaction path.

## Migration Plan

1. Add new settings with defaults and treat legacy compact threshold settings as ignored deprecated input.
2. Extend session index writing to include compaction/accounting metadata; ignore old `activeTokens` when checkpoint metadata is present.
3. Implement compaction archive paths without changing current active session path conventions.
4. Replace `compact_session()` internals with the new compaction service; remove the placeholder behavior entirely.
5. Remove compact/trimming behavior from `session_input_callback` and route auto compact through the pre-run context service.
6. Update `deepy status`, session listings, and context footer to read the new token estimate fields.
7. Archive rollback is file-level: if replacement write fails, move the rotated JSONL back to the original path and leave index metadata unchanged.

## Open Questions

- Should manual `/compact` be available in non-interactive `deepy sessions compact <id>` form in the first implementation, or only interactive?
- Should the default recent preservation policy be expressed as message count, token budget, or both in the public config?
- Should archived pre-compaction JSONL files be exposed through `deepy sessions show`, or only kept as recovery artifacts on disk?
