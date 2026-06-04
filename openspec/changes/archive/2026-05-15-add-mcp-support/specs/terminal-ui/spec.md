## ADDED Requirements

### Requirement: MCP Command Discoverability
Deepy SHALL make MCP status discoverable in interactive command surfaces.

#### Scenario: Slash command completions are built
- **WHEN** Deepy builds slash command completions
- **THEN** `/mcp` SHALL be included as a built-in command

#### Scenario: User asks for help
- **WHEN** a user runs `/help`
- **THEN** Deepy SHALL include `/mcp` in the command list
- **AND** the description SHALL indicate that it shows MCP server status and
  tools

### Requirement: MCP Status Display
Deepy SHALL provide a concise `/mcp` status view for configured MCP servers.

#### Scenario: User opens MCP status
- **WHEN** a user runs `/mcp`
- **THEN** Deepy SHALL show configured MCP servers with their connection state
- **AND** it SHALL show tool counts for active servers
- **AND** it SHALL show concise failure reasons for failed or invalid servers

#### Scenario: Active MCP tools are available
- **WHEN** a configured MCP server is active and exposes tools
- **THEN** `/mcp` SHALL show model-visible MCP tool names
- **AND** preferred MCP web-search tools SHALL be visually identifiable in the
  status output

#### Scenario: MCP has no configured servers
- **WHEN** a user runs `/mcp` and no MCP servers are configured
- **THEN** Deepy SHALL show a concise message explaining that no MCP servers are
  configured

#### Scenario: MCP status includes secrets
- **WHEN** MCP server configuration contains environment variables, headers, or
  token-like values
- **THEN** `/mcp` SHALL NOT print plaintext secret values

### Requirement: MCP Runtime Status
Deepy SHALL surface MCP availability without overwhelming normal chat output.

#### Scenario: Startup screen is shown
- **WHEN** Deepy starts interactive mode
- **AND** MCP is enabled
- **THEN** the welcome or status surface SHALL show a concise MCP availability
  summary

#### Scenario: Bottom toolbar is shown
- **WHEN** MCP servers are active in an interactive session
- **THEN** the bottom toolbar MAY include a concise MCP-loaded indicator
- **AND** the indicator SHALL NOT replace context window usage or AGENTS.md
  status information
