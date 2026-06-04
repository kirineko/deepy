## ADDED Requirements

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
