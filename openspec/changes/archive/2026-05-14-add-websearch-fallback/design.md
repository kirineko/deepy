## Context

Deepy's WebSearch tool currently provides self-owned web research capability.
DuckDuckGo is a useful default because it does not require users to bring an API
key, but some users cannot connect to it reliably. The tool should let users
configure a reachable SearXNG instance as the preferred provider while keeping
DuckDuckGo as the fallback when SearXNG is not configured or fails.

The fallback must fit the existing tool model: the model invokes one WebSearch
tool, Deepy chooses providers internally, and the returned tool result remains
structured and safe to show.

## Goals / Non-Goals

**Goals:**

- Use configured SearXNG first.
- Fall back to DuckDuckGo when SearXNG fails due to timeout, DNS, connection
  error, non-2xx response, parser failure, or empty results.
- Use DuckDuckGo directly when no SearXNG URL is configured.
- Stop using legacy `command` and `api_url` execution paths.
- Preserve clear result metadata so users can see which provider succeeded or
  why all providers failed.
- Avoid printing secrets from configured fallback endpoints or headers.
- Cover the behavior with deterministic unit tests.

**Non-Goals:**

- Add a dependency on DeepCode or any third-party private backend.
- Require every user to configure a paid search API.
- Implement browser automation or JavaScript-rendered search result scraping.
- Change the model-visible WebSearch tool name or its high-level purpose.

## Decisions

1. Provider chain rather than one hard-coded provider.

   Deepy should model search as an ordered provider chain: configured SearXNG
   first, then DuckDuckGo. This keeps the implementation extensible without
   changing the tool schema again if more providers are added later.

2. Configuration-driven primary provider.

   SearXNG should be configured through the existing `tools.web_search` config
   block. A configured endpoint is more reliable than baking in a public search
   domain that may be blocked for the same users.

3. Failure classes are retryable only when they indicate provider unavailability.

   The fallback should trigger for connectivity and unusable-response failures:
   timeout, DNS/connection failure, HTTP non-2xx, malformed response, parser
   failure, or empty results. It should not hide local validation errors such as
   an empty query.

4. Tool result metadata should include provider attempts.

   On success, metadata should include the successful provider and prior failed
   attempts. On complete failure, the returned error should summarize all
   providers attempted. Secrets in URLs, headers, and query strings must be
   masked.

## Risks / Trade-offs

- Fallback configuration may be under-specified -> Document supported config
  fields in tool docs and tests.
- Another public default fallback may also be blocked -> Prefer configurable
  fallback over relying on one more hard-coded public site.
- Too much failure metadata can pollute model context -> Keep metadata concise
  and mask sensitive values.
- Fallback retries increase latency -> Use short provider timeouts and stop on
  first usable result.

## Migration Plan

1. Add provider-chain internals behind the existing WebSearch tool.
2. Add configuration parsing for `tools.web_search.searxng_url`.
3. Update WebSearch tool documentation so the model understands fallback behavior
   but still calls the same tool.
4. Stop routing WebSearch through legacy `command` and `api_url`.
5. Add tests for SearXNG success, SearXNG failure with DuckDuckGo success, and
   all providers failing.
6. No user migration is required for zero-config users; they continue to use
   DuckDuckGo.

## Open Questions

- Should SearXNG timeout be separately configurable, or should it reuse the
  existing WebSearch timeout?
