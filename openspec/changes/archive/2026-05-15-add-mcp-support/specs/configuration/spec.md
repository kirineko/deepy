## ADDED Requirements

### Requirement: MCP Configuration Files
Deepy SHALL separate Deepy MCP policy from MCP server definitions.

#### Scenario: Deepy MCP policy is loaded
- **WHEN** Deepy loads persistent configuration
- **THEN** it SHALL read Deepy MCP policy from `~/.deepy/config.toml`
- **AND** the policy SHALL include whether MCP is enabled, connection timeouts,
  cleanup timeouts, MCP session read timeout, tool-list caching preference,
  project-config permission, and MCP web-search preference settings

#### Scenario: Global MCP server definitions are loaded
- **WHEN** MCP is enabled and `~/.deepy/mcp.json` exists
- **THEN** Deepy SHALL read MCP server definitions from the file's `mcpServers`
  object
- **AND** it SHALL support server entries that define stdio or Streamable HTTP
  transports

#### Scenario: MCP server definition file is missing
- **WHEN** MCP is enabled and `~/.deepy/mcp.json` does not exist
- **THEN** Deepy SHALL treat the configured MCP server list as empty
- **AND** it SHALL continue without an error

#### Scenario: Deepy config is shown
- **WHEN** a user runs `deepy config show` or `deepy config show --json`
- **THEN** Deepy SHALL include resolved MCP policy values
- **AND** it SHALL NOT include plaintext secret values from MCP server
  environment variables or headers

### Requirement: MCP Server Definition Validation
Deepy SHALL validate MCP server definitions before creating SDK MCP server
instances.

#### Scenario: Stdio server definition is valid
- **WHEN** an enabled MCP server definition has `transport = "stdio"` or omits
  transport while providing a command
- **THEN** Deepy SHALL require a non-empty command
- **AND** it SHALL accept optional args, env, roles, and tool preference metadata

#### Scenario: Streamable HTTP server definition is valid
- **WHEN** an enabled MCP server definition has `transport = "streamable_http"`
- **THEN** Deepy SHALL require a non-empty URL
- **AND** it SHALL accept optional headers, roles, and tool preference metadata

#### Scenario: MCP server definition is invalid
- **WHEN** an enabled MCP server definition is missing required fields for its
  transport or uses an unsupported transport
- **THEN** Deepy SHALL skip that server
- **AND** it SHALL record a concise validation error for status display

#### Scenario: Environment variable placeholder is configured
- **WHEN** an MCP server env or header value uses a placeholder such as
  `${TAVILY_API_KEY}`
- **THEN** Deepy SHALL resolve it from the process environment before creating
  the MCP server
- **AND** unresolved placeholders SHALL cause that server to be skipped with a
  concise validation error
