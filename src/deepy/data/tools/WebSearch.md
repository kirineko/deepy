## WebSearch

Search when current or external information is required.

Args: `query`.

Uses `tools.web_search.searxng_url` when configured, otherwise uses Deepy's
default SearXNG endpoint. Requests include browser-like headers so private
SearXNG instances with limiter enabled are less likely to reject the request as
bot traffic. If SearXNG cannot be reached or returns no parseable results, falls
back to Deepy's built-in DuckDuckGo HTML search implementation.

If MCP web-search tools are listed in the system prompt, prefer those MCP tools
first for web/current-information searches. Use this built-in WebSearch as the
fallback when MCP search is unavailable, fails, or the user explicitly asks for
Deepy's built-in search.

Keep searches targeted. After several successful searches, stop searching and
synthesize from the gathered sources. Use `WebFetch` for exact URLs that need
deeper reading instead of continuing broad search queries.
