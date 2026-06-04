# mcp-support Specification

## Purpose
TBD - created by archiving change add-mcp-support. Update Purpose after archive.
## Requirements
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

### Requirement: Search-Class MCP Inheritance For Subagents

Deepy SHALL allow search-oriented subagents to inherit only search-class MCP
tools by default.

#### Scenario: Explore subagent is constructed with preferred MCP search tools

- **WHEN** active MCP servers expose tools that Deepy identifies as preferred
  web/search tools
- **AND** Deepy constructs the `explore` subagent
- **THEN** Deepy SHALL make those search-class MCP tools available to `explore`
- **AND** it SHALL preserve deterministic server-prefixed MCP tool names

#### Scenario: Non-search MCP tools are active

- **WHEN** active MCP servers expose tools that are not identified as
  search-class tools
- **AND** Deepy constructs a subagent
- **THEN** Deepy SHALL NOT automatically inherit those tools into the subagent
  tool set

#### Scenario: Custom subagent disables search MCP inheritance

- **WHEN** a custom subagent definition sets search MCP inheritance to false
- **THEN** Deepy SHALL NOT expose search-class MCP tools to that subagent unless
  they are otherwise explicitly allowed by supported policy

#### Scenario: Search MCP inheritance is reported

- **WHEN** Deepy reports available tools or subagent configuration diagnostics
- **THEN** it SHOULD identify whether search-class MCP tools were inherited by a
  subagent
- **AND** it SHALL NOT print secret values from MCP configuration

### Requirement: MCP Tool Audit Enforcement

Deepy SHALL apply the active system audit mode to MCP tool calls through OpenAI
Agents SDK MCP approval support.

#### Scenario: Normal mode gates MCP tools

- **WHEN** the active audit mode is `normal`
- **AND** an active MCP server exposes a tool to the SDK agent
- **THEN** Deepy SHALL configure that MCP tool to require approval before
  execution

#### Scenario: Auto mode gates untrusted MCP tools

- **WHEN** the active audit mode is `auto`
- **AND** an active MCP server exposes a tool that is not explicitly configured
  as safe for automatic approval
- **THEN** Deepy SHALL configure that MCP tool to require approval before
  execution

#### Scenario: Auto mode allows configured safe MCP tools

- **WHEN** the active audit mode is `auto`
- **AND** an MCP server/tool pair is explicitly configured as safe for automatic
  approval
- **THEN** Deepy SHALL allow that MCP tool call to proceed without a user
  approval prompt

#### Scenario: Yolo mode allows MCP tools

- **WHEN** the active audit mode is `yolo`
- **AND** an active MCP server exposes a tool to the SDK agent
- **THEN** Deepy SHALL configure that MCP tool so the SDK does not require user
  approval before execution

### Requirement: MCP Approval Identity

Deepy SHALL identify MCP approval requests with stable server and tool context.

#### Scenario: MCP approval is shown to the user

- **WHEN** an SDK run pauses for an MCP tool approval
- **THEN** Deepy SHALL show the MCP server name, model-visible tool name,
  original tool name when known, and arguments summary
- **AND** Deepy SHALL preserve deterministic server-prefixed naming when MCP
  server tool names would otherwise collide

#### Scenario: MCP approval decision is resolved

- **WHEN** the user approves or rejects an MCP tool approval
- **THEN** Deepy SHALL resolve the SDK MCP approval interruption on the paused
  run state
- **AND** Deepy SHALL resume the original top-level run

### Requirement: MCP Safe Tool Configuration

Deepy SHALL support exact MCP approval overrides for auto mode.

#### Scenario: Safe MCP tool is configured

- **WHEN** TOML configuration marks a specific MCP server/tool pair as safe for
  automatic approval
- **THEN** Deepy SHALL apply that override only to the matching server/tool pair
- **AND** Deepy SHALL NOT treat other tools on the same server as safe unless
  they are also explicitly configured

#### Scenario: Safe MCP tool configuration is stale

- **WHEN** TOML configuration references an MCP server/tool pair that is not
  active in the current session
- **THEN** Deepy SHALL ignore that approval override for tool execution
- **AND** status surfaces MAY report that the configured override did not match
  an active tool

