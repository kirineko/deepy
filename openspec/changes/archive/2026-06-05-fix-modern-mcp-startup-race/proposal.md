## Why

In Modern UI, MCP servers are connected in a Textual worker started from `on_mount`,
while the first model turn runs as an `exclusive` worker in the same worker group.
If the user submits a prompt before the startup connection finishes, the exclusive
turn worker cancels the in-flight MCP connection worker, the turn runs with no active
MCP servers, and `DeepyMcpRuntime` stays latched in a connected-but-failed state so MCP
never loads again for the rest of the session. Classic UI does not hit this because it
connects on a persistent runtime loop and blocks on connection readiness before each turn.

## What Changes

- Isolate the Modern UI MCP startup worker from the exclusive model-turn worker group so
  starting the first turn no longer cancels the in-flight MCP connection.
- Make `DeepyMcpRuntime.connect()` resilient: a connection attempt that is cancelled or
  fails before completing SHALL NOT permanently latch the runtime; a later attempt SHALL be
  able to connect successfully.
- Ensure a Modern UI model turn that depends on MCP observes connected servers by awaiting
  MCP readiness before constructing the agent (aligning Modern UI behavior with Classic UI).
- Add regression coverage for the "submit prompt during MCP startup" race in Modern UI and
  for the retryable-connect behavior in the runtime.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `mcp-support`: MCP connection lifecycle must be retryable after an interrupted or failed
  connection attempt instead of permanently latching into a never-connected state.
- `experimental-textual-tui`: Modern UI MCP startup connection must survive the start of the
  first model turn, and a turn that relies on MCP must observe connected servers.

## Impact

- `src/deepy/mcp.py`: `DeepyMcpRuntime.connect()` connection-state handling.
- `src/deepy/ui/modern/app.py`: MCP startup worker group and model-turn readiness gating.
- Tests under `tests/` covering MCP runtime reconnect and Modern UI startup race.
- No config schema, CLI surface, or MCP file format changes.
