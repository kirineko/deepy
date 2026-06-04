## Why

Deepy already parses DeepSeek cache usage, but the current session flow does not
make cacheable prefix stability a first-class invariant. Agent construction,
tool availability, runtime prompt blocks, retries, and compaction can change the
effective request prefix without a recorded reason, which makes long sessions
more expensive and harder to diagnose.

DeepSeek-Reasonix demonstrates a stronger pattern: stable immutable prefix,
append-only log, volatile scratch, cache-aligned folding, and cache hit telemetry.
Deepy should adopt the useful parts of that architecture while preserving the
OpenAI Agents SDK boundary and existing provider abstractions.

## What Changes

- Introduce a DeepSeek cache-first context model with an explicit stable prefix
  fingerprint, append-only session-log invariant, and volatile scratch boundary.
- Record cache-breaking context changes such as compaction rewrites, retry or
  interrupt recovery, MCP tool-set changes, skill/rule/context changes, and new
  sessions.
- Make cache-aligned folding/compaction reuse the active conversation provider,
  model, and model settings so provider cache namespaces stay aligned.
- Add a diagnostic spike path to compare Deepy's canonical prefix snapshot with
  the request shape produced through the OpenAI Agents SDK, without logging
  secrets.
- Persist and display cache health: per-turn hit/miss tokens, session-level hit
  ratio, prefix generation, and the last cache-break reason.
- Add focused tests and an optional live DeepSeek cache probe gated by
  environment variables. The normal test suite SHALL NOT require network access
  or a real API key.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `deepseek-provider`: adds DeepSeek cache-prefix fingerprinting, SDK request
  shape diagnostics, and active-model-aligned auxiliary compaction behavior.
- `session-context`: adds cache-first context invariants, cache-break recording,
  and cache-aligned folding semantics.
- `terminal-ui`: adds cache health and cache-break visibility to the default
  Rich/prompt-toolkit UI surfaces.
- `experimental-textual-tui`: adds the same cache health and cache-break
  visibility to the opt-in Textual TUI.

## Impact

- Affected code: `src/deepy/llm/runner.py`, `src/deepy/llm/context.py`,
  `src/deepy/llm/compaction.py`, provider/model-settings builders, usage
  parsing, session SQLite storage, slash command status/session renderers, and
  Textual TUI state/rendering.
- Affected data: session metadata gains cache prefix generation, fingerprint,
  cache-break reason, and aggregate cache usage fields.
- Affected tests: provider request-shape tests, session context tests,
  compaction/folding tests, usage aggregation tests, default UI tests, and
  Textual TUI tests.
- No dependency change is expected for the proposal itself. Any implementation
  dependency addition must be justified in `design.md` before coding.
