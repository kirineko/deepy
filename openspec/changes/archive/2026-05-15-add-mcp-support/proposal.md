## Why

Users need Deepy to reuse the growing MCP ecosystem instead of relying only on
Deepy's built-in tools. A near-term requirement is allowing a configured Tavily
MCP search server to become the preferred web search path, while keeping
Deepy's built-in WebSearch available as a fallback.

## What Changes

- Add MCP server configuration and loading for Deepy, using OpenAI Agents SDK
  MCP server support instead of implementing a custom MCP protocol client.
- Support global MCP server definitions with stdio and Streamable HTTP
  transports.
- Add MCP lifecycle management for interactive and one-shot runs, including
  connection status, failed-server degradation, and cleanup on exit.
- Add `/mcp` terminal visibility so users can inspect configured servers,
  connection state, tool counts, and exposed tool names.
- Prefer configured MCP web-search tools, such as Tavily MCP, over Deepy's
  built-in WebSearch while preserving built-in WebSearch as a fallback.
- Keep project-level MCP configuration disabled by default because stdio MCP
  servers can launch local processes.

## Capabilities

### New Capabilities

- `mcp-support`: Covers MCP server configuration, OpenAI Agents SDK integration,
  server lifecycle, tool exposure, and MCP-specific safety boundaries.

### Modified Capabilities

- `configuration`: Add MCP config locations, file formats, timeout settings,
  and safe defaults.
- `tools`: Add MCP web-search preference behavior relative to built-in WebSearch.
- `terminal-ui`: Add `/mcp` discoverability and status display for configured
  MCP servers.

## Impact

- Affected code areas include settings loading, agent construction, interactive
  runner lifecycle, one-shot runner lifecycle, slash command handling, status
  rendering, and tests.
- New runtime dependency surface uses OpenAI Agents SDK MCP classes:
  `MCPServerStdio`, `MCPServerStreamableHttp`, and `MCPServerManager`.
- MCP stdio configuration can start local subprocesses, so project-level MCP
  config must be treated as a trust boundary and remain opt-in.
