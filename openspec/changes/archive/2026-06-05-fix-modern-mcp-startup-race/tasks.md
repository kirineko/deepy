## 1. Make the MCP runtime connect retryable

- [x] 1.1 In `src/deepy/mcp.py`, stop latching `self.connected = True` before
  `connect_all()` completes; introduce a single-flight in-progress guard so concurrent
  callers coordinate instead of each flipping the latch.
- [x] 1.2 Ensure a cancelled or failed connection attempt resets connection state so a
  later `connect()` retries, while a successful attempt still ends with `connected == True`
  and reuse semantics unchanged.
- [x] 1.3 Preserve existing per-server failure recording and the disabled/invalid status
  paths.

## 2. Isolate the Modern UI MCP startup worker

- [x] 2.1 In `src/deepy/ui/modern/app.py`, start the MCP startup worker in a dedicated
  worker group so the exclusive `run_model_turn` worker no longer cancels it.
- [x] 2.2 Confirm cleanup on exit still cancels/cleans the MCP runtime regardless of group.

## 3. Gate the first MCP-dependent turn on readiness

- [x] 3.1 Before constructing the agent in the Modern UI turn path, await the shared MCP
  runtime connection (idempotent once connected) so an early prompt observes active servers.
- [x] 3.2 Keep the wait bounded by existing connect timeouts and degrade to built-in tools
  when no server becomes active.

## 4. Tests

- [x] 4.1 Add a runtime regression test: a cancelled/failed first `connect()` followed by a
  second `connect()` that succeeds and exposes active servers.
- [x] 4.2 Add a Modern UI test simulating a prompt submitted during MCP startup, asserting
  the startup connection is not cancelled and MCP servers remain available.
- [x] 4.3 Run `uv run ruff check src tests`, `uv run ty check src`, and the focused MCP/TUI
  test modules.

## 5. Validate and document

- [x] 5.1 Run `openspec validate fix-modern-mcp-startup-race --type change --strict`.
- [x] 5.2 Update any user-facing docs only if behavior text references MCP startup; otherwise
  no doc change.
