## 1. Configuration

- [x] 1.1 Add MCP policy dataclasses to settings for enabled state, timeouts, tool-list caching, project-config permission, and web-search preference.
- [x] 1.2 Add `~/.deepy/mcp.json` discovery and parsing for `mcpServers` server definitions.
- [x] 1.3 Validate stdio and Streamable HTTP MCP server definitions, including required fields, unsupported transport handling, enabled flags, roles, and concise error reporting.
- [x] 1.4 Resolve environment/header placeholders such as `${TAVILY_API_KEY}` without exposing plaintext secret values in config display or logs.
- [x] 1.5 Extend `deepy config show` and JSON status output to include resolved MCP policy while masking MCP secrets.
- [x] 1.6 Add configuration tests for default behavior, valid stdio config, valid Streamable HTTP config, missing config file, invalid server definitions, unresolved placeholders, and masked output.

## 2. MCP Runtime

- [x] 2.1 Add an MCP runtime module that maps validated server definitions to OpenAI Agents SDK `MCPServerStdio` and `MCPServerStreamableHttp` instances.
- [x] 2.2 Use `MCPServerManager` with configured connect/cleanup timeouts, failed-server degradation, active server tracking, and status/error capture.
- [x] 2.3 Update `build_deepy_agent()` to accept active MCP servers and pass them through `Agent.mcp_servers` with server-prefixed MCP tool names enabled.
- [x] 2.4 Keep built-in tools registered through the existing `build_function_tools()` path without wrapping MCP tools as Deepy `FunctionTool`s.
- [x] 2.5 Wire one-shot `deepy run` to create, connect, use, and close an MCP manager for the invocation.
- [x] 2.6 Wire interactive mode to create one MCP manager per process, reuse active MCP connections across turns, and close the manager on `/exit`, Ctrl+D confirmation, and KeyboardInterrupt.
- [x] 2.7 Add runtime tests for successful server activation, failed-server degradation, no-server fallback, one-shot cleanup, and interactive exit cleanup.

## 3. Web Search Preference

- [x] 3.1 Detect preferred MCP web-search tools from explicit config, `web_search` roles, and Tavily/search name heuristics.
- [x] 3.2 Add dynamic system-prompt guidance naming active preferred MCP web-search tools and instructing the model to use them before built-in WebSearch.
- [x] 3.3 Adjust built-in WebSearch model-facing description so it is described as a fallback when MCP web search is active.
- [x] 3.4 Preserve built-in WebFetch and WebSearch fallback behavior when MCP search is unavailable, fails, or no MCP web-search tool is active.
- [x] 3.5 Add tests proving Tavily/search MCP tools are preferred in prompt/tool guidance and built-in WebSearch remains available.

## 4. Terminal UI

- [x] 4.1 Add `/mcp` to slash command completions, `/help`, and relevant welcome/status surfaces.
- [x] 4.2 Implement `/mcp` status display with configured server names, connection states, active tool counts, model-visible tool names, and failure reasons.
- [x] 4.3 Mark preferred MCP web-search tools in `/mcp` output without printing secrets.
- [x] 4.4 Add a concise MCP availability indicator to interactive status surfaces without replacing Context Window or `AGENTS.md loaded` information.
- [x] 4.5 Add terminal UI tests for `/mcp` help/completion, no-server output, active-server output, failed-server output, preferred web-search marker, and secret masking.

## 5. Documentation And Validation

- [x] 5.1 Update README and README.zh-CN with MCP config file locations, sample Tavily MCP config, security notes, and `/mcp` usage.
- [x] 5.2 Document that project-level MCP config is ignored by default and requires an explicit global opt-in.
- [x] 5.3 Add or update tool documentation for MCP web-search preference and built-in WebSearch fallback behavior.
- [x] 5.4 Run focused tests for settings, MCP runtime, tool registration, web-search guidance, CLI run cleanup, and terminal UI.
- [x] 5.5 Run `openspec validate add-mcp-support --strict` before marking the change ready for implementation review.
