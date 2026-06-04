## Why

Some users cannot reach DuckDuckGo reliably because of regional network
conditions, DNS failures, timeouts, or upstream blocking. Deepy's WebSearch tool
should allow users to configure a reachable SearXNG instance as the first search
provider, while still retaining DuckDuckGo as a zero-config fallback.

## What Changes

- Add a configurable SearXNG provider path so users can choose a reachable
  endpoint in constrained networks.
- Use configured SearXNG first, then fall back to DuckDuckGo when SearXNG cannot
  be reached or returns an unusable response.
- Stop using legacy `command` and `api_url` WebSearch execution paths.
- Return clear provider/error metadata when all providers fail, without exposing
  secrets or crashing the interactive session.
- Add tests for primary success, primary failure with fallback success, and all
  providers failing.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tools`: WebSearch behavior changes to configured SearXNG first, DuckDuckGo
  fallback second, with clear failure reporting.

## Impact

- Affected code: WebSearch implementation, web search configuration, generated
  config, tool result metadata, and related tests.
- Affected user experience: WebSearch can use a configured SearXNG instance for
  users who cannot connect to DuckDuckGo reliably.
- No breaking CLI changes are expected.
