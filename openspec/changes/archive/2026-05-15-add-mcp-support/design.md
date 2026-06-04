## Context

Deepy currently constructs an OpenAI Agents SDK `Agent` with Deepy's built-in
function tools only. Web search is provided by Deepy's built-in `WebSearch`
implementation, which uses configured SearXNG first and DuckDuckGo as fallback.

MCP introduces a second tool source. Official MCP architecture treats Deepy as
the host, with one MCP client connection per configured MCP server. The local
OpenAI Agents SDK already supports this model through `MCPServerStdio`,
`MCPServerStreamableHttp`, `MCPServerSse`, `MCPServerManager`, `Agent.mcp_servers`,
and `Agent.mcp_config`. This change should use those SDK primitives rather than
implementing Deepy's own JSON-RPC MCP client.

The most important initial user flow is Tavily MCP search. If a user configures
a Tavily or other web-search MCP server, Deepy should steer the model toward
that MCP tool before built-in `WebSearch`, while still keeping built-in search
available when MCP is unavailable or fails.

## Goals / Non-Goals

**Goals:**

- Load configured MCP servers through OpenAI Agents SDK MCP primitives.
- Support stdio and Streamable HTTP transports in the first implementation.
- Provide global MCP config with safe defaults and clear secret handling.
- Keep project-level MCP config disabled unless explicitly allowed.
- Expose MCP tools to the model with deterministic server-prefixed names.
- Prefer configured MCP web-search tools over built-in `WebSearch`.
- Make MCP state inspectable through `/mcp` and normal status surfaces.
- Clean up MCP subprocesses/connections on all normal interactive exits.

**Non-Goals:**

- No custom MCP protocol implementation.
- No MCP marketplace or automatic server installation.
- No hosted MCP tool integration in the first version.
- No OAuth flow for remote MCP servers in the first version.
- No MCP resources/prompts UI beyond what is needed to expose tools.
- No automatic trust of project-provided MCP command configs.

## Decisions

1. **Use OpenAI Agents SDK MCP classes as the runtime integration layer.**

   Deepy will map config entries into `MCPServerStdio` or
   `MCPServerStreamableHttp`, connect them with `MCPServerManager`, and pass
   `manager.active_servers` into `Agent(mcp_servers=...)`. The agent will set
   `mcp_config.include_server_in_tool_names = True` so local MCP tools appear as
   deterministic names following the Agents SDK prefixing rule, such as
   `mcp_tavily__tavily_search`.

   Alternative considered: write a Deepy MCP client similar to
   `reference/deepcode-cli-js`. That gives full control, but duplicates SDK
   behavior and puts protocol lifecycle, schema conversion, retries, tool
   output mapping, and cleanup on Deepy.

2. **Keep Deepy's built-in tools and MCP tools as separate tool sources.**

   `build_function_tools()` should continue to return only Deepy's built-in
   tools. `build_deepy_agent()` should accept an optional MCP server list and
   pass it to the SDK agent. This keeps existing tool tests and behavior stable
   and lets the SDK handle MCP tool listing and invocation.

   Alternative considered: convert MCP tools into Deepy `FunctionTool` objects.
   That would make all tools look uniform locally, but it would lose SDK MCP
   features such as native output mapping, MCP tracing, approval settings, and
   manager lifecycle behavior.

3. **Use two config files: Deepy policy in TOML and MCP server definitions in JSON.**

   Deepy policy remains in `~/.deepy/config.toml` under `[mcp]`, matching the
   existing TOML-only Deepy config requirement. MCP server definitions live in
   `~/.deepy/mcp.json` using the ecosystem-standard `mcpServers` shape:

   ```json
   {
     "mcpServers": {
       "tavily": {
         "transport": "stdio",
         "command": "npx",
         "args": ["-y", "tavily-mcp"],
         "env": {"TAVILY_API_KEY": "${TAVILY_API_KEY}"},
         "roles": ["web_search"]
       }
     }
   }
   ```

   The JSON file is not a replacement for Deepy's TOML config. It is a
   dedicated MCP interoperability file so users can copy existing `mcpServers`
   blocks from other clients with minimal editing.

   Alternative considered: place all server definitions in TOML. That would be
   simpler for Deepy's parser but worse for MCP ecosystem compatibility.

4. **Treat project MCP config as a trust boundary.**

   The first implementation loads only global MCP servers by default. Project
   MCP config may be introduced as `<project>/.deepy/mcp.json`, but Deepy must
   ignore it unless `mcp.allow_project_config = true` is set in global config.
   Stdio MCP servers execute local commands, so a cloned repository must not
   be able to auto-start arbitrary MCP processes just by being the current
   directory.

   Alternative considered: follow some clients and merge user/project MCP
   config automatically. That is convenient, but it gives repositories too much
   implicit execution power for Deepy's current UX.

5. **Use explicit role metadata plus heuristics for web-search preference.**

   Server definitions may include Deepy-local `roles = ["web_search"]` or a
   configured preferred server/tool in TOML. If explicit metadata is absent,
   Deepy may infer a web-search MCP candidate from server or tool names
   containing `tavily`, `search`, or `web_search`.

   When one or more MCP web-search tools are active, Deepy will add prompt
   guidance telling the model to prefer those tools over built-in `WebSearch`.
   The built-in `WebSearch` description should also be softened to indicate it
   is a fallback when MCP web search is active. Built-in `WebFetch` remains
   available because MCP search results often need direct URL fetching.

   Alternative considered: disable built-in `WebSearch` when Tavily MCP is
   present. That removes fallback reliability and makes transient MCP failures
   worse.

6. **Keep MCP connection lifecycle outside individual model turns where possible.**

   Interactive mode should create a manager once per process, connect configured
   servers before the first model turn, reuse active connections across turns,
   and close them on `/exit`, Ctrl-D, and KeyboardInterrupt. One-shot `deepy run`
   should create a manager for that invocation and close it afterward.

   Alternative considered: connect/disconnect MCP servers inside each
   `run_prompt_once()` call. That is easier to scope but adds significant
   startup latency and can lose MCP server state between turns.

## Risks / Trade-offs

- **Stdio MCP config can execute arbitrary local commands** -> Load only global
  MCP config by default, mask secrets, and keep project config opt-in.
- **MCP startup or tool calls can be slow** -> Use `MCPServerManager` connect
  and cleanup timeouts plus the SDK MCP session read timeout, failed-server drop
  behavior, and concise status messages; add background loading later only if
  startup latency is unacceptable.
- **Tool name collisions can confuse the model** -> Enable SDK server-prefixed
  MCP tool names.
- **MCP web-search preference may not be followed by the model every time** ->
  Apply both system-prompt guidance and fallback wording in built-in
  `WebSearch`; expose active MCP search tools in status for debuggability.
- **MCP subprocess cleanup can be fragile** -> Centralize manager ownership and
  add tests for `/exit`, Ctrl-D, KeyboardInterrupt, failed startup, and one-shot
  cleanup paths.
- **Users may paste non-Deepy MCP JSON fields** -> Preserve compatibility by
  accepting common `mcpServers` fields and ignoring unknown Deepy-irrelevant
  fields unless they create unsafe ambiguity.
