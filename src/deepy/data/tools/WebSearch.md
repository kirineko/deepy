## WebSearch

Search when current or external information is required.

Args: `query`.

Uses the configured local command first, then configured API endpoint if present. If
neither is configured, uses Deepy's built-in local web search implementation and
returns parsed search result titles, URLs, and snippets.
