## Why

Deepy stable terminal startup currently waits for the version update check and
MCP connection before rendering the welcome screen. Slow network checks or MCP
server startup can therefore make the CLI appear stuck before the user sees any
interactive UI.

This change makes the first screen and prompt appear quickly while preserving
stable tool availability before the first model turn.

## What Changes

- Render the welcome screen before startup network update checks complete.
- Start the prompt loop without waiting for MCP connection to complete.
- Show startup progress as ghost-style footer state, such as update checking and
  MCP connecting.
- When a newer version is found before prompt input starts, include it in the
  welcome state; when it is found after prompt input starts, show a short
  prompt-toolkit-safe terminal notification instead of redrawing the full
  welcome panel.
- Connect MCP in the background, but wait for MCP readiness before the first
  model turn that depends on MCP-capable tool registration.
- Refresh the footer when MCP completes so the bottom status changes from a
  connecting state to the connected MCP count.
- Keep MCP connection, model calls, and MCP cleanup on the same async runtime
  boundary so MCP server/session objects are not used across incompatible event
  loops.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: Startup welcome, prompt readiness, version update notification,
  MCP startup progress, and first-turn MCP readiness behavior change.

## Impact

- Affected stable terminal UI code:
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/prompt_input.py`
  - `src/deepy/ui/status_footer.py`
  - `src/deepy/ui/welcome.py`
- Affected startup integration points:
  - `src/deepy/update_check.py`
  - `src/deepy/mcp.py`
  - `src/deepy/llm/runner.py`
- Affected tests:
  - `tests/test_terminal_ui.py`
  - possibly focused tests for prompt toolbar/footer behavior and startup order
- No model prompt, tool schema, session history, or public CLI command change is
  intended.
