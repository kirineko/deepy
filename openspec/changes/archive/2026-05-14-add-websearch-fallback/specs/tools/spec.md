## MODIFIED Requirements

### Requirement: Web Research

Deepy SHALL provide self-owned web search and direct URL fetch tools instead of
depending on third-party DeepCode backends. WebSearch SHALL use a configured
SearXNG instance first when `tools.web_search.searxng_url` is set, and SHALL
fall back to DuckDuckGo when SearXNG is unreachable or returns an unusable
response. WebSearch SHALL use DuckDuckGo directly when no SearXNG URL is
configured.

#### Scenario: User asks for current online information

- **WHEN** the model invokes web search or fetch
- **THEN** Deepy SHALL use its own configured implementation
- **AND** a complete URL SHALL be fetchable through the web fetch tool

#### Scenario: SearXNG search succeeds

- **WHEN** the model invokes WebSearch and configured SearXNG returns usable results
- **THEN** Deepy SHALL return those results
- **AND** the tool metadata SHALL identify SearXNG as the successful provider

#### Scenario: SearXNG is unreachable and DuckDuckGo fallback succeeds

- **WHEN** the model invokes WebSearch and configured SearXNG fails because of timeout,
  DNS failure, connection failure, HTTP non-2xx, malformed response, parser
  failure, or empty results
- **AND** DuckDuckGo returns usable results
- **THEN** Deepy SHALL return the DuckDuckGo results
- **AND** the tool metadata SHALL identify DuckDuckGo and summarize the failed
  SearXNG attempt

#### Scenario: No SearXNG configured

- **WHEN** the model invokes WebSearch and no SearXNG URL is configured
- **THEN** Deepy SHALL use DuckDuckGo directly

#### Scenario: All search providers fail

- **WHEN** the model invokes WebSearch and every configured provider fails
- **THEN** Deepy SHALL return a structured tool failure
- **AND** the failure SHALL include concise, masked provider-attempt metadata
- **AND** the interactive session SHALL continue without an uncaught exception
