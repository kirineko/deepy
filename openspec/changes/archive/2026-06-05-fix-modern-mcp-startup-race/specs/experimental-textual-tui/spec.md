## ADDED Requirements

### Requirement: Modern UI MCP Startup Resilience
The Modern UI SHALL connect configured MCP servers at startup without allowing the
first model turn to abort that connection, and a turn that relies on MCP SHALL observe
connected servers.

#### Scenario: Prompt submitted during MCP startup
- **WHEN** the user submits a prompt in Modern UI before the startup MCP connection
  has finished
- **THEN** starting the model turn SHALL NOT cancel the in-flight MCP connection
- **AND** MCP servers that connect successfully SHALL remain available for that turn
  and subsequent turns in the session

#### Scenario: First MCP-dependent turn waits for connection readiness
- **WHEN** Modern UI begins a model turn while the startup MCP connection is still
  in progress
- **THEN** Deepy SHALL await MCP connection readiness before constructing the agent
  for that turn
- **AND** the agent SHALL be constructed with the MCP servers that became active

#### Scenario: MCP remains usable after an early prompt
- **WHEN** an early prompt during startup would previously have interrupted MCP
  connection
- **THEN** `/mcp` SHALL report the connected MCP servers and their tools after the
  connection completes
- **AND** Deepy SHALL NOT remain in a state where MCP can never load for the rest of
  the session
