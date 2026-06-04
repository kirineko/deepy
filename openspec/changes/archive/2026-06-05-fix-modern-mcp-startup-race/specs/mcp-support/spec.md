## MODIFIED Requirements

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

#### Scenario: MCP connection attempt is interrupted before completion
- **WHEN** an in-progress MCP connection attempt is cancelled or fails before it
  finishes connecting configured servers
- **THEN** Deepy SHALL NOT leave the MCP runtime permanently marked as connected
  while no servers are active
- **AND** a subsequent connection attempt on the same runtime SHALL be able to
  connect the configured servers successfully

#### Scenario: Interactive mode exits
- **WHEN** the user exits interactive mode through `/exit`, Ctrl+D confirmation,
  or KeyboardInterrupt
- **THEN** Deepy SHALL close active MCP server connections and subprocesses
  before returning from the interactive process
