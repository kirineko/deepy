## Context

DeepSeek context caching rewards exact reusable request prefixes. The reference
project, DeepSeek-Reasonix, protects that by splitting context into an immutable
prefix, an append-only log, and volatile scratch. Deepy has some compatible
pieces already: system prompt ordering keeps stable instructions before dynamic
runtime context, usage parsing exposes cache hit/miss tokens, and SQLite session
storage can persist structured metadata.

The gap is that Deepy currently delegates final request construction to the
OpenAI Agents SDK and treats compaction as an active-history rewrite. That means
Deepy cannot simply copy Reasonix's raw payload design; it needs an explicit
canonical prefix snapshot at Deepy's boundary plus a spike to verify how closely
that snapshot matches the SDK request shape.

## Goals / Non-Goals

**Goals:**

- Make DeepSeek cache health measurable and explainable per session.
- Keep normal turns append-only unless an operation explicitly records a cache
  break.
- Prefer cache-friendly summary/fold calls that reuse the stable prefix and the
  active conversation model/settings.
- Preserve the OpenAI Agents SDK model path unless the spike proves it blocks
  the requirements.
- Keep live network probes optional and secret-safe.

**Non-Goals:**

- Replacing the OpenAI Agents SDK with a custom Chat Completions client in this
  change.
- Guaranteeing identical cache behavior for OpenRouter, Xiaomi, or other
  third-party providers.
- Adding vector memory, retrieval, or semantic cache systems.
- Persisting API keys, live probe transcripts, or provider payloads.
- Changing the default user-facing model selection.

## Decisions

### 1. Add a canonical prefix snapshot instead of raw payload ownership

Deepy will introduce a cache-prefix snapshot object at the runner/provider
boundary. It will fingerprint the stable components that Deepy controls:
system instructions, ordered built-in tools, ordered MCP tools, model id,
provider settings that affect request shape, selected skill/rule/prompt blocks,
and any few-shot or prefix input if present.

Rationale: Deepy can test and reason about this snapshot without depending on
private SDK internals. A diagnostic path will compare the snapshot against the
SDK-produced request shape where possible.

Alternative considered: bypass the SDK and build raw DeepSeek requests. That
would offer maximum byte control but is a larger provider rewrite and risks
breaking tool-call, streaming, and usage behavior already covered by specs.

### 2. Persist cache state as session metadata

SQLite session storage will persist cache context metadata alongside existing
items: prefix fingerprint, prefix generation, latest cache-break reason,
per-turn hit/miss tokens, session aggregate hit/miss tokens, and last observed
cache hit ratio.

Rationale: cache behavior needs to survive resume/history flows and feed `/status`,
session listings, compaction decisions, and TUI state. This is metadata, not
model-visible transcript content.

Alternative considered: compute everything from transcript events at display
time. That loses explicit break reasons and makes resume behavior dependent on
expensive replay.

### 3. Treat rewrites as explicit cache breaks

Normal model turns append user, assistant, reasoning, tool call, and tool result
items. Operations that mutate existing active history, such as compaction,
retry rollback, interrupt cleanup, or archive-and-replace, will record a cache
break and increment prefix/log generation metadata.

Rationale: some rewrites are necessary for correctness or token control, but
they should be visible and testable instead of silently harming cache reuse.

Alternative considered: ban all rewrites. That is not practical because Deepy
already supports compaction and recovery workflows.

### 4. Make compaction cache-aligned with the active model

For DeepSeek sessions, summary/fold calls will use the active conversation
provider, model, and model settings. The fold request should reuse the same
stable prefix snapshot and ordered tools where the SDK permits it, keep head
conversation content unchanged in the summary request, and append the
summarization instruction at the end.

Rationale: DeepSeek prompt cache is model-scoped, so switching a summary/fold
call to a different model can reduce the main conversation model's cache reuse.
Keeping the auxiliary call on the active model makes the cache boundary
predictable.

Alternative considered: summarize with the active conversation model and active
thinking mode. This is the chosen behavior because cache-hit correctness matters
more than a cheaper isolated auxiliary summary call.

### 5. Add optional live probe, keep normal tests offline

The implementation will include an optional script or diagnostic command that
can run against a selected DeepSeek model when `DEEPSEEK_API_KEY` is set in the environment.
The normal suite will rely on deterministic unit and integration tests with no
network.

Rationale: cache hit behavior ultimately depends on provider behavior, but CI
and local development must not require secrets.

Alternative considered: require a live probe as part of validation. That would
make tests flaky and unsafe for contributors.

## Risks / Trade-offs

- SDK payload opacity -> Mitigation: add a spike task and test-only capture
  boundary before relying on fingerprint assumptions.
- Dynamic MCP tool ordering changes prefix bytes -> Mitigation: canonicalize
  ordering at Deepy's boundary and record tool-set changes as cache breaks.
- Compaction still rewrites active history -> Mitigation: record the break,
  reuse the stable prefix during the summary call, and expose the reason in UI.
- Extra metadata can drift from real usage -> Mitigation: update cache metadata
  only from normalized usage events and covered session-storage tests.
- Auxiliary calls using a cheaper different model would not warm the active
  model's cache -> Mitigation: keep compaction/fold on the active provider,
  model, and model settings.
- Secrets could leak during live spike -> Mitigation: accept keys only through
  environment variables and never persist request payloads or headers.

## Migration Plan

1. Add metadata fields with defaults for existing SQLite sessions so old
   sessions load with unknown cache state.
2. Introduce prefix snapshots and cache-break events without changing transcript
   replay semantics.
3. Route compaction through cache-aware auxiliary settings that preserve the
   active provider/model boundary.
4. Add UI display once metadata is available.
5. Keep rollback simple: existing session items remain valid, and cache metadata
   can be ignored by older code paths.

## Open Questions

- How much of the SDK-produced request payload can be inspected in tests without
  private monkeypatching?
- Should runtime project/git context remain part of the stable prefix, or should
  changing runtime context always be modelled as a prefix-generation break?
- Should MCP tool ordering be preserved as discovered or sorted into a canonical
  provider order?
