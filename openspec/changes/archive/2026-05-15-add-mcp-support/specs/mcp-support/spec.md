## ADDED Requirements

### Requirement: MCP Server Loading
Deepy SHALL load configured MCP servers through OpenAI Agents SDK MCP server
primitives rather than through a custom MCP JSON-RPC implementation.

#### Scenario: Stdio MCP server is configured
- **WHEN** global MCP configuration includes an enabled stdio server with a
  command and optional arguments
- **THEN** Deepy SHALL create an OpenAI Agents SDK stdio MCP server for that
  entry
- **AND** it SHALL pass the active connected server to the model agent through
  the SDK MCP server interface

#### Scenario: Streamable HTTP MCP server is configured
- **WHEN** global MCP configuration includes an enabled Streamable HTTP server
  with a URL and optional headers
- **THEN** Deepy SHALL create an OpenAI Agents SDK Streamable HTTP MCP server for
  that entry
- **AND** it SHALL pass the active connected server to the model agent through
  the SDK MCP server interface

#### Scenario: MCP servers expose duplicate tool names
- **WHEN** multiple active MCP servers expose the same original tool name
- **THEN** Deepy SHALL configure the SDK agent to include the server name in MCP
  tool names
- **AND** the model-visible MCP tool names SHALL be deterministic and
  server-prefixed

### Requirement: MCP Lifecycle Management
Deepy SHALL manage MCP server connection lifecycle for both interactive and
one-shot model runs.

#### Scenario: Interactive mode starts with MCP enabled
- **WHEN** Deepy starts interactive mode and MCP is enabled with configured
  servers
- **THEN** Deepy SHALL connect configured MCP servers before the first model turn
  or report that no MCP servers became active
- **AND** it SHALL reuse active MCP server connections across turns in that
  interactive process

#### Scenario: One-shot run uses MCP
- **WHEN** `deepy run` executes with MCP enabled and configured servers
- **THEN** Deepy SHALL connect MCP servers for that invocation
- **AND** it SHALL close MCP server connections before the command exits

#### Scenario: MCP server connection fails
- **WHEN** one configured MCP server fails to connect
- **THEN** Deepy SHALL continue with other successfully connected MCP servers
- **AND** it SHALL record a concise failure reason for status display
- **AND** it SHALL NOT fail the entire Deepy session solely because one MCP
  server failed

#### Scenario: Interactive mode exits
- **WHEN** the user exits interactive mode through `/exit`, Ctrl+D confirmation,
  or KeyboardInterrupt
- **THEN** Deepy SHALL close active MCP server connections and subprocesses
  before returning from the interactive process

### Requirement: MCP Tool Exposure
Deepy SHALL expose active MCP tools to the model through OpenAI Agents SDK MCP
tool discovery.

#### Scenario: MCP tools are active
- **WHEN** the model agent is constructed after MCP servers have connected
- **THEN** Deepy SHALL provide the active MCP servers to the OpenAI Agents SDK
  agent
- **AND** the SDK SHALL be responsible for MCP tool discovery and tool calls

#### Scenario: No MCP servers are active
- **WHEN** MCP is disabled, no servers are configured, or every configured
  server fails
- **THEN** Deepy SHALL construct the model agent with built-in tools only
- **AND** ordinary model turns SHALL continue to work

### Requirement: MCP Safety Boundary
Deepy SHALL treat MCP stdio server configuration as a trusted local execution
boundary.

#### Scenario: Global MCP config defines stdio command
- **WHEN** a user configures a stdio MCP server in the global MCP config
- **THEN** Deepy MAY start that command as part of MCP initialization
- **AND** Deepy SHALL NOT print environment secret values in normal output,
  status output, or debug logs

#### Scenario: Project MCP config exists by default
- **WHEN** a project contains MCP server configuration
- **AND** project MCP config is not explicitly enabled in global Deepy config
- **THEN** Deepy SHALL ignore the project MCP server configuration
- **AND** it SHALL NOT start any server command from that project config

#### Scenario: Project MCP config is explicitly enabled
- **WHEN** global Deepy config explicitly enables project MCP config
- **AND** the project contains valid MCP server configuration
- **THEN** Deepy MAY merge the project MCP servers with global MCP servers
- **AND** project server definitions SHALL NOT cause secret values to be printed
  in normal output, status output, or debug logs
