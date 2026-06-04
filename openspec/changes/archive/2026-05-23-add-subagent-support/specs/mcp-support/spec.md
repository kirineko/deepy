## ADDED Requirements

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
