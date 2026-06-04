## Context

Deepy currently tracks three related but different token concepts:

- API usage returned by the model provider (`prompt_tokens`, `completion_tokens`, cache tokens, reasoning tokens, request count).
- Local history estimate (`active_tokens`, `last_usage_tokens`, `pending_tokens`) used as internal fallback and post-compaction fit validation.
- Terminal context status shown to the user.

The current UI labels make these concepts look like one value. Cline separates them more clearly: the Context Window display is based on the latest API request's token footprint, while Token Usage is cumulative usage across the task. Deepy should adopt that mental model and use Context Window pressure as the automatic compaction timing signal.

## Goals / Non-Goals

**Goals:**

- Introduce explicit data semantics for latest request context window usage and cumulative token usage.
- Present Context Window as the latest model request's occupancy of the configured window.
- Present Token Usage as cumulative API consumption, including cache and reasoning fields when known.
- Trigger automatic compaction from latest Context Window used tokens when available.
- Keep the terminal UI concise while making the token source clear.

**Non-Goals:**

- Do not change `compact_trigger_ratio` itself.
- Do not add a new provider dependency or tokenizer dependency.
- Do not change command names, session file format compatibility, or compaction summary behavior.
- Do not require exact pre-request tokenization when provider usage is unavailable; estimates remain acceptable fallback data.

## Decisions

### Decision 1: Use three named token domains

Deepy will treat token data as two user-facing domains:

```text
Latest Request Context
  prompt/input + completion/output + cache writes + cache reads
  -> shown as Context Window used/total/remaining
  -> used for automatic compaction timing when available

Cumulative Token Usage
  accumulated provider usage across requests
  -> shown as Token Usage
```

Rationale: Cline's UI is easier to understand because "Context Window" is not cumulative. Once Context Window usage exists, keeping a second visible compact pressure number creates unnecessary confusion.

Alternative considered: Keep an additional visible compaction pressure segment. That preserves previous Deepy visibility but duplicates context pressure concepts and conflicts with the Cline-style model.

### Decision 2: Derive Context Window from the latest request usage snapshot

When provider usage is known, the latest request context total will be:

```text
input_context_tokens + completion_tokens

where input_context_tokens = prompt_tokens when available,
or prompt_cache_miss_tokens + prompt_cache_hit_tokens when prompt_tokens is unavailable.
```

For SDK-style fields, use equivalent normalized input/output/cache fields without double counting cache detail fields that are already included in the provider's input total. Reasoning tokens are reported under Token Usage, but do not inflate Context Window unless the provider reports them as part of output/completion totals.

Rationale: This matches Cline's `tokensIn + tokensOut + cacheWrites + cacheReads` display model while preserving Deepy's current normalized field names.

Alternative considered: Use `total_tokens` directly. This is simpler, but it loses the ability to explain input, output, cache, and reasoning contributions and can hide provider-specific differences.

### Decision 3: Keep cumulative usage as the accounting source

`TokenUsage` remains the normalized accounting object for per-turn and session totals. It should preserve request-level entries so the UI can show latest request values and cumulative values without recomputing from unrelated session metadata.

Rationale: Deepy already normalizes provider usage and stores request entries. Reusing that path keeps implementation narrow.

Alternative considered: Add a separate usage ledger format. That would be cleaner long-term but is unnecessary for this refactor.

### Decision 4: Use Context Window usage for auto compact timing

Automatic compaction uses latest Context Window used tokens when provider usage exists:

```text
latest_context_used >= window_tokens * compact_trigger_ratio
```

If latest Context Window usage is unavailable, Deepy may fall back to the local history estimate to avoid sending obviously oversized first or legacy requests. After compaction, Deepy validates the compacted session using the rewritten session estimate rather than the stale pre-compaction latest request.

Rationale: This makes the displayed Context Window number and the next auto-compact timing consistent.

Alternative considered: Continue using effective session pressure for auto compact while showing Context Window in the UI. That would leave users seeing one pressure number while compaction uses another.

## Risks / Trade-offs

- [Risk] Provider usage fields differ in whether cache/reasoning tokens are included in totals. → Mitigation: normalize once in `TokenUsage`, document whether each field contributes to latest request context, and add tests for DeepSeek and SDK-style payloads.
- [Risk] Users may not know when compaction is imminent. → Mitigation: append `compact next` to the Context Window segment when latest Context Window usage is at or above the configured threshold.
- [Risk] Latest request usage may be unknown for failed or provider-omitted usage events. → Mitigation: show Context Window as unknown or estimated instead of falling back to cumulative usage.
- [Risk] Existing tests assume bottom toolbar context equals compaction pressure. → Mitigation: update tests to assert both the new Cline-style Context Window semantics and unchanged auto compact trigger behavior.

## Migration Plan

- Add or refine usage helpers that expose latest request context usage and cumulative token usage from existing `TokenUsage` data.
- Update session index writes only if needed to persist latest request usage snapshots; otherwise derive them from existing request usage entries.
- Update terminal rendering text and tests.
- Verify automatic compaction triggers from latest Context Window usage and no longer displays a separate compact pressure segment.

Rollback is straightforward: revert the display/helper changes while leaving persisted usage fields compatible.

## Open Questions

- Should Token Usage display session cumulative totals in the toolbar, or only in the per-turn footer?
