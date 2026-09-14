## MODIFIED Requirements

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
  using the independent DeepSeek Messages search service

## ADDED Requirements

### Requirement: Bounded DeepSeek Search Execution
Deepy SHALL bound search work and keep opaque server data out of ordinary model and UI output.

#### Scenario: Default bounds
- **WHEN** WebSearch starts a request
- **THEN** it SHALL set max_uses to 3 and max_tokens to 4096, use an overall timeout of 60 seconds, and expose at most 10 deduplicated sources
- **AND** it SHALL send only the search query context rather than the entire conversation
- **AND** it SHALL NOT automatically retry the complete paid request

#### Scenario: Cancellation
- **WHEN** the user cancels while search is pending
- **THEN** Deepy SHALL cancel the pending request and return control without starting fallback searches

#### Scenario: Encrypted or absent excerpts
- **WHEN** a source contains encrypted content but no plaintext snippet
- **THEN** Deepy SHALL preserve its valid title/URL without inventing an excerpt
- **AND** it SHALL NOT expose encrypted blobs or credentials in normal output

#### Scenario: Domain constraints
- **WHEN** search results are returned
- **THEN** Deepy SHALL NOT claim a server-enforced domain restriction without locally validating that restriction

### Requirement: DeepSeek Built-In Web Research
Deepy SHALL provide built-in WebSearch through a separate DeepSeek Anthropic Messages search service and preserve direct URL WebFetch.

#### Scenario: Built-in search invocation
- **WHEN** any supported conversation model invokes WebSearch
- **THEN** Deepy SHALL call `https://api.deepseek.com/anthropic/v1/messages` with model `deepseek-flash` and native tool `web_search_20250305`
- **AND** it SHALL use only the DeepSeek profile/environment credentials, independently of active conversation credentials or base URL
- **AND** it SHALL return structured sources from actual search tool records

#### Scenario: Search success
- **WHEN** the response contains correlated server search invocation and successful search result blocks
- **THEN** Deepy SHALL return source titles and valid HTTP(S) URLs with available plaintext snippets/citations
- **AND** it SHALL identify DeepSeek as the backend and distinguish complete, empty and partial results

#### Scenario: No evidence
- **WHEN** the response is HTTP 200 or claims to search but has no actual search tool records
- **THEN** Deepy SHALL return a structured recoverable failure instead of claiming a successful search

#### Scenario: Tool error
- **WHEN** the request fails, a server search tool reports an error, or results are incomplete
- **THEN** Deepy SHALL expose a concise masked error or explicitly marked partial result
- **AND** it SHALL keep the session alive and SHALL NOT silently retry against another backend

#### Scenario: Missing search key
- **WHEN** DeepSeek credentials are unavailable
- **THEN** WebSearch SHALL return an actionable instruction to configure the DeepSeek profile or DEEPSEEK_API_KEY
- **AND** non-DeepSeek conversation, MCP tools and WebFetch SHALL remain usable

#### Scenario: Legacy search removal
- **WHEN** built-in search is invoked or its configuration is loaded
- **THEN** Deepy SHALL NOT contact SearXNG, s.kirineko.tech, or DuckDuckGo and SHALL NOT perform the old query-rewriting model call
- **AND** it SHALL NOT mount conversation-provider native search tools

#### Scenario: Direct URL fetch
- **WHEN** the model invokes WebFetch with a complete URL
- **THEN** Deepy SHALL preserve local HTTP fetching and readable extraction
- **AND** it SHALL NOT submit an unsupported DeepSeek native web_fetch tool

### Requirement: Responses Read Image Follow-Up
Deepy's existing image follow-up messages from `Read` SHALL remain compatible with the shared image input contract.

#### Scenario: Read loads an image file
- **WHEN** the model invokes `Read` for a supported image file
- **THEN** Deepy SHALL return a structured follow-up message containing image content
- **AND** the image content SHALL use the same internal image attachment representation accepted by model input normalization

#### Scenario: Read image follow-up is converted for Responses
- **WHEN** a `Read` image follow-up message is included in model input for a supported image model
- **THEN** Deepy SHALL convert it to the same Responses input_image shape used for pasted prompt images
- **AND** it SHALL preserve the base64 data URL and MIME type

#### Scenario: Read image follow-up targets unsupported model
- **WHEN** a `Read` image follow-up message would be sent to a model that does not support image input
- **THEN** Deepy SHALL avoid sending image content blocks to that model
- **AND** it SHALL surface a concise model incompatibility error rather than sending an unsupported payload

#### Scenario: Tool image exceeds active limits
- **WHEN** a Read image result exceeds the active model or request image limits
- **THEN** Deepy SHALL return a recoverable image-limit error without sending the invalid image payload

## REMOVED Requirements

### Requirement: Web Research
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "DeepSeek Built-In Web Research" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.

### Requirement: Read Tool Image Follow-Up Compatibility
**Reason**: This change intentionally replaces the former provider/API/configuration contract and its obsolete scenarios.
**Migration**: Use "Responses Read Image Follow-Up" in this capability. Reconfigure removed provider IDs and legacy formats explicitly; no old protocol fallback is retained.
