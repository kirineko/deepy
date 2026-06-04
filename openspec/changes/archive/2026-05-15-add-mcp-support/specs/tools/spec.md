## ADDED Requirements

### Requirement: MCP Web Search Preference
Deepy SHALL prefer configured MCP web-search tools over built-in WebSearch while
preserving built-in WebSearch as a fallback.

#### Scenario: MCP web-search tool is active
- **WHEN** one or more active MCP tools are identified as web-search tools
- **THEN** Deepy's model instructions SHALL tell the model to prefer those MCP
  tools for web or current-information searches
- **AND** built-in WebSearch SHALL remain available as a fallback

#### Scenario: Tavily MCP server is active
- **WHEN** an active MCP server is explicitly configured with the `web_search`
  role or identified as a Tavily/search server
- **THEN** Deepy SHALL identify its search-capable MCP tools as preferred web
  search tools
- **AND** the model-facing guidance SHALL name those preferred MCP tools when
  possible

#### Scenario: Preferred MCP search fails during a turn
- **WHEN** a preferred MCP web-search tool fails, times out, or is unavailable
  during a model turn
- **THEN** the model MAY use built-in WebSearch to complete the search task
- **AND** Deepy SHALL keep the interactive session alive

#### Scenario: No MCP web-search tool is active
- **WHEN** MCP is disabled, no MCP web-search tools are active, or every MCP
  web-search server fails to connect
- **THEN** Deepy's built-in WebSearch SHALL keep its normal provider behavior
  using configured SearXNG and DuckDuckGo fallback
