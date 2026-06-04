## Context

Deepy currently has a read-only DeepSeek balance lookup used by `/status`.
Interactive exit summaries are intentionally local-only today: they show model
usage, suggestion usage, model name, and session identity, but they do not call
or display DeepSeek balance data.

The requested feature changes that boundary. The useful user-facing value is
not another `/status` balance row, but the amount of account balance consumed
during the interactive session. DeepSeek's balance endpoint returns string
decimal balances per currency, so the implementation should treat provider
balances as decimal money values rather than floats.

## Goals / Non-Goals

**Goals:**

- Show session cost in stable and experimental exit summary panels.
- Use balance snapshots from DeepSeek's official `/user/balance` endpoint.
- Keep cost metadata separate from Token Usage and Context Window accounting.
- Preserve graceful failure behavior when balance lookup is unavailable.
- Avoid leaking API keys in status, summary, logs, or error text.

**Non-Goals:**

- Do not estimate cost from model price tables or token usage.
- Do not add a new pricing catalog, config field, or public CLI flag.
- Do not block exit on a slow or failed balance lookup.
- Do not claim the delta is exclusively caused by Deepy if the same account is
  used concurrently elsewhere.
- Do not change ordinary model execution, provider settings, or `/status`
  formatting beyond shared balance helpers if needed.

## Decisions

### Use balance delta snapshots, not token-price estimates

Record a starting balance snapshot when an interactive session becomes cost
trackable, then record an ending balance snapshot when the user exits. Compute
per-currency spend as:

```text
spent = start.total_balance - end.total_balance
```

Only positive deltas should be displayed as spend. Zero or negative deltas
should be displayed as no measurable spend or unavailable, depending on whether
the snapshots were otherwise valid.

Alternative considered: estimate from Token Usage and a local model pricing
table. That would avoid an exit-time network call, but it would drift when
provider pricing, cache discounts, or model routing changes. Balance deltas are
closer to what the user actually paid.

### Persist cost snapshots as session metadata

Store cost snapshot metadata in the session index, separate from `usage`,
`inputSuggestionUsage`, active token estimates, and latest Context Window
checkpoint fields. The metadata should include currency, starting total balance,
ending total balance, computed spent amount, availability reason if any, and
timestamps for the snapshots.

Alternative considered: only compute cost in memory at exit. That works for the
immediate panel, but it prevents tests and later session views from inspecting
the recorded summary and makes interrupted exit paths harder to reason about.

### Keep lookup failures non-fatal and concise

Both start and end snapshots may fail because of missing API key, unsupported
host, timeout, HTTP error, network failure, or malformed response. The exit
summary should remain visible and may show concise cost unavailable text when a
cost was expected but cannot be computed.

Alternative considered: silently omit the cost row on any failure. That keeps
the panel cleaner, but it hides why the user did not see the feature.

### Label the value as an account balance delta

The summary text should make the accounting source clear. If the same DeepSeek
account is used by other clients during the session, the balance delta can
include that external activity. The UI should use concise wording such as
`session cost` with detail text or metadata indicating that it is based on the
DeepSeek account balance delta.

## Risks / Trade-offs

- [Risk] Concurrent use of the same DeepSeek account can inflate the session
  cost. -> Mitigation: document and label the value as an account balance delta.
- [Risk] Exit-time network calls can slow shutdown. -> Mitigation: reuse the
  short balance timeout and never block summary rendering on uncaught errors.
- [Risk] Floating point arithmetic can produce money rounding errors. ->
  Mitigation: parse balance strings with `Decimal` and preserve display strings
  where possible.
- [Risk] Existing tests assert exit summaries do not fetch balance. ->
  Mitigation: update those tests to cover the new deliberate snapshot boundary
  while preserving non-exit/non-status no-fetch behavior.

## Migration Plan

Existing session indexes without cost metadata remain valid. The new fields are
optional and should be omitted or ignored when absent. Rollback is safe because
older code will ignore unknown JSON fields in the session index.

## Open Questions

None.
