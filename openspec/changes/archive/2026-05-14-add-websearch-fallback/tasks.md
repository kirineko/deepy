## 1. Existing Behavior Review

- [x] 1.1 Locate the current WebSearch implementation, configuration parsing,
  and tool documentation.
- [x] 1.2 Identify current DuckDuckGo request, parsing, timeout, and error paths.

## 2. Provider Fallback Implementation

- [x] 2.1 Introduce an ordered WebSearch provider chain with configured SearXNG first.
- [x] 2.2 Add configuration support for `tools.web_search.searxng_url`.
- [x] 2.3 Treat timeout, DNS/connection failure, HTTP non-2xx, malformed response,
  parser failure, and empty results as fallback-eligible provider failures.
- [x] 2.4 Preserve local validation errors, such as an empty query, without
  retrying unrelated providers.
- [x] 2.5 Return concise provider-attempt metadata on success and failure, with
  secrets masked.

## 3. Documentation And Model Guidance

- [x] 3.1 Update WebSearch tool documentation to describe fallback behavior and
  provider metadata.
- [x] 3.2 Update user-facing configuration documentation if new fallback config
  fields are added.

## 4. Verification

- [x] 4.1 Add tests for DuckDuckGo success when SearXNG is not configured.
- [x] 4.2 Add tests for SearXNG success and SearXNG failure followed by DuckDuckGo success.
- [x] 4.3 Add tests for all providers failing with structured, masked error
  metadata.
- [x] 4.4 Run `uv run pytest`, `uv run ruff check`, and `uv run pyright`.
