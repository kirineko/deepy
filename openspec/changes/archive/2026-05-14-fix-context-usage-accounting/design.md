## Context

Deepy currently tracks two related but different quantities:

- Per-turn API usage: model billing/telemetry data such as input, output, cache, reasoning, request count, and total tokens.
- Session context occupancy: the estimated tokens that will be replayed into the next model request.

The bug comes from collapsing these quantities. `DeepyJsonlSession.record_usage()` stores the latest turn's normalized `prompt_tokens` as `activeTokens` and `lastUsageTokens`. The terminal toolbar reads `activeTokens`, and pre-run auto compaction reads `session.context_token_state().active_tokens`. A short follow-up turn can therefore lower the displayed `ctx` and lower the auto-compaction trigger input, even though the persisted session has grown.

`reference/kimi-cli` keeps a better boundary: `Context` owns `token_count`, `_pending_token_estimate`, and `token_count_with_pending`; `_usage` records update the precise checkpoint and clear pending estimates; automatic compaction reads `token_count_with_pending`; UI status formats `context_tokens / max_context_tokens`.

## Goals / Non-Goals

**Goals:**

- Make `ctx` represent current session context pressure, not latest turn cost.
- Ensure normal user/assistant/tool appends never make context occupancy go backward.
- Keep auto compaction and bottom toolbar display on the same effective-token source.
- Preserve precise provider usage for the per-turn footer and accumulated session usage totals.
- Repair or avoid stale undercounted session index values without requiring users to delete old sessions.

**Non-Goals:**

- Changing model provider behavior, pricing display, or usage normalization semantics.
- Implementing tokenizer-perfect local counting for every provider.
- Changing `/compact`, `/resume`, `/new`, or configuration command syntax.
- Removing cache hit/miss or reasoning token reporting.

## Decisions

### Keep separate accounting channels

Deepy will treat `TokenUsage` as API accounting and session token state as context accounting. `usage.total_tokens` and accumulated session usage remain visible cost/telemetry fields. `activeTokens`/`lastUsageTokens` represent effective context occupancy checkpoints only.

Alternative considered: use API `total_tokens` for `ctx`. Rejected because output tokens are generated after the request starts and are not the same as pre-request context occupancy.

### Derive context occupancy from replayable session state plus checkpoints

The effective context token count will be computed as:

```
effective_context_tokens = checkpoint_context_tokens + pending_estimated_tokens
```

where pending tokens are estimated from records appended after the checkpoint. On restore, Deepy should reconstruct this from session JSONL and index metadata. If checkpoint metadata is missing or obviously stale, Deepy should fall back to estimating replayable records rather than trusting a smaller latest-turn usage value.

Alternative considered: always estimate the whole JSONL file. Rejected as a primary path because provider usage gives a better checkpoint after a real model request, and full estimation can be more expensive for long sessions. It remains a useful fallback and migration repair path.

### Do not reduce context occupancy on ordinary usage records

Recording usage after a normal successful turn must not lower context occupancy below the prior effective context plus the newly appended assistant/tool records covered by the turn. Context may decrease only through explicit history-changing operations: compaction, clearing, new session, undo/truncation, or equivalent session rewrite.

Alternative considered: trust the provider's latest input token count exactly. Rejected because the observed SDK/provider usage may reflect a single request, a partial request, cached/request shape differences, or a compacted model input path; it is not a safe monotonic session state replacement.

### Align UI and compaction with one source

The bottom toolbar and `ensure_context_ready()` should use the same effective session context token state. The toolbar may label the number as approximate, but it must not be driven by accumulated usage total or latest short-turn usage.

Alternative considered: keep toolbar as a usage display and compaction as a separate estimate. Rejected because the current user-facing `ctx` is interpreted as compaction pressure, and showing a different number from the trigger source makes debugging impossible.

### Preserve compaction reset semantics

After manual or automatic compaction rewrites a session, the replacement history establishes a new context checkpoint. The compacted summary token count can use compaction model output tokens for the generated summary plus local estimates for preserved messages, matching the existing Deepy approach and Kimi's `CompactionResult.estimated_token_count` pattern.

## Risks / Trade-offs

- Existing index metadata may already contain undercounted `activeTokens` -> Recompute from JSONL when metadata is missing, inconsistent, or smaller than a safe estimate for pending records.
- Local token estimates can be inaccurate for CJK, tool payloads, and provider-specific tokenizers -> Keep approximate UI labeling and let precise checkpoints improve the estimate after real model calls.
- Multi-request turns can report accumulated SDK usage differently from streamed usage events -> Normalize request usage for the footer, but only use context checkpoint data under monotonic constraints.
- Conservative counting may trigger compaction earlier than before -> Prefer early compaction over silently missing the trigger and sending oversized requests.

## Migration Plan

1. Add regression tests that reproduce the screenshot behavior: a large turn followed by a short turn must not shrink `ctx` or reduce auto-compaction readiness.
2. Introduce or adjust session token-state helpers so context occupancy is computed independently from accumulated API usage.
3. Update `record_usage()` and append/replace paths to maintain context checkpoints and pending estimates under monotonic rules.
4. Point toolbar rendering and pre-run auto compaction at the same effective token state.
5. Keep reading old session index fields, but repair stale entries opportunistically when the JSONL-derived estimate is safer.
6. Validate targeted tests, then run the relevant session/context, runner, usage, and terminal UI test groups.
