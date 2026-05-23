# Deepy MCP Configuration

Deepy supports MCP servers through the OpenAI Agents SDK. Deepy does not
implement its own MCP protocol client; it maps your configuration to SDK MCP
servers and passes connected servers to the agent.

Deepy uses two files:

- `~/.deepy/config.toml`: Deepy MCP policy and preference settings.
- `~/.deepy/mcp.json`: MCP server definitions using the common `mcpServers`
  shape.

Project MCP config is ignored by default. If explicitly enabled, Deepy also
loads `<project>/.deepy/mcp.json`.

## Minimal Tavily Setup

Set your API key in the shell:

```bash
export TAVILY_API_KEY="tvly-your-key"
```

Create `~/.deepy/mcp.json`:

```json
{
  "mcpServers": {
    "tavily": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "tavily-mcp@latest"],
      "env": {
        "TAVILY_API_KEY": "${TAVILY_API_KEY}"
      },
      "roles": ["web_search"]
    }
  }
}
```

Start Deepy and run:

```text
/mcp
```

You should see the `tavily` server and its model-visible MCP tools.

## `~/.deepy/config.toml`

All MCP policy fields are optional. Deepy has in-memory defaults, so most users
only need `~/.deepy/mcp.json`.

```toml
[mcp]
enabled = true
connect_timeout_seconds = 10
cleanup_timeout_seconds = 10
client_session_timeout_seconds = 30
cache_tools_list = true
allow_project_config = false
prefer_mcp_web_search = true

[mcp.web_search]
prefer_mcp = true
preferred_server = ""
preferred_tools = []
fallback_to_builtin = true
```

### `[mcp]` Fields

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `enabled` | boolean | `true` | Enables MCP loading. Set to `false` to disable all MCP servers. |
| `connect_timeout_seconds` | number | `10` | Timeout for connecting each MCP server. |
| `cleanup_timeout_seconds` | number | `10` | Timeout for closing MCP servers during exit. |
| `client_session_timeout_seconds` | number | `30` | SDK MCP session read timeout. This affects slow `tools/list` and `tools/call` responses. Increase this if MCP tools time out while waiting for a response. |
| `cache_tools_list` | boolean | `true` | Lets the SDK cache MCP tool lists for lower per-turn latency. |
| `allow_project_config` | boolean | `false` | Allows `<project>/.deepy/mcp.json` to be loaded. Keep disabled unless you trust the project. |
| `prefer_mcp_web_search` | boolean | `true` | Enables Deepy web-search preference guidance for detected MCP search tools. |

### `[mcp.web_search]` Fields

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `prefer_mcp` | boolean | `true` | Prefer detected MCP web-search tools over built-in `WebSearch`. |
| `preferred_server` | string | empty | Optional MCP server name to prefer, matching a key in `mcpServers`. |
| `preferred_tools` | string array | `[]` | Optional tool-name allow list for preferred MCP web search. |
| `fallback_to_builtin` | boolean | `true` | Keep built-in `WebSearch` available if MCP search is unavailable or fails. |

Preference order:

1. `preferred_server` / `preferred_tools`
2. `roles = ["web_search"]` in `mcp.json`
3. Name heuristics: server/tool/description contains `tavily`, `search`,
   `web_search`, or `web-search`

## `~/.deepy/mcp.json`

Top-level shape:

```json
{
  "mcpServers": {
    "server-name": {
      "transport": "stdio"
    }
  }
}
```

The `server-name` becomes part of the model-visible tool name. For example, a
server named `tavily` with tool `tavily_search` is exposed as:

```text
mcp_tavily__tavily_search
```

Server names may contain letters, numbers, `.`, `_`, and `-`.

### Common Server Fields

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `enabled` | boolean | `true` | Set to `false` to keep a server in config but skip it. |
| `transport` | string | inferred | `stdio` or `streamable_http`. If omitted and `command` exists, Deepy uses `stdio`; otherwise it uses `streamable_http`. |
| `roles` | string array | `[]` | Deepy-local metadata. Use `["web_search"]` to mark a server as preferred search. |
| `preferred_tools` | string array | `[]` | Deepy-local metadata for preferred tool names on this server. |

Unknown fields are ignored by Deepy unless they make the server definition
ambiguous or invalid.

### Stdio Server Fields

```json
{
  "mcpServers": {
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/project"],
      "cwd": "/path/to/project",
      "env": {
        "TOKEN": "${TOKEN}"
      }
    }
  }
}
```

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `command` | string | yes | Command used to start the MCP server. |
| `args` | string array | no | Arguments passed to `command`. |
| `cwd` | string | no | Working directory for the MCP server process. |
| `env` | object | no | Environment variables for the server process. |

Stdio MCP servers start local commands. Treat them as trusted code.

### Streamable HTTP Server Fields

```json
{
  "mcpServers": {
    "remote-search": {
      "transport": "streamable_http",
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_TOKEN}"
      },
      "roles": ["web_search"]
    }
  }
}
```

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `url` | string | yes | Streamable HTTP MCP endpoint. |
| `headers` | object | no | HTTP headers sent to the MCP server. |

`transport = "http"` is accepted as an alias for `streamable_http`.

## Environment Placeholders

`env` and `headers` values may reference shell environment variables:

```json
{
  "TAVILY_API_KEY": "${TAVILY_API_KEY}"
}
```

If the environment variable is missing, Deepy skips that server and shows a
validation error in `/mcp`.

Deepy does not print plaintext `env` or `headers` values in `/mcp`, status
output, or normal config display.

## Project Config

Project MCP config path:

```text
<project>/.deepy/mcp.json
```

It is ignored by default. To enable it globally:

```toml
[mcp]
allow_project_config = true
```

Only enable project MCP config for repositories you trust. A project-level stdio
server can start local commands.

## Subagent Search Inheritance

The built-in `explore` subagent may inherit only MCP tools that Deepy has
identified as preferred web/search tools. Deepy keeps deterministic
server-prefixed names such as `mcp_tavily__tavily_search` and does not pass
non-search MCP tools to subagents by default.

Custom subagents can opt out:

```md
---
name: docs-research
description: Search docs and summarize references.
mcp:
  inherit_search: false
---

Read-only research instructions.
```

This inheritance does not expose MCP secrets in status output.

## Troubleshooting

Use `/mcp` inside Deepy to inspect server state, tool names, and validation
errors.

For Tavily local stdio setup, check:

```bash
node --version
npx --version
npx -y tavily-mcp@latest
```

If `npx` is not found, install Node.js or use the full path to `npx` in
`command`.
