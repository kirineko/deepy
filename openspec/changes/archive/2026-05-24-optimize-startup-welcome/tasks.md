## 1. Startup State And UI Plumbing

- [x] 1.1 Add a stable terminal startup state model for update-check and MCP
  readiness states.
- [x] 1.2 Extend status footer construction to render startup ghost segments for
  pending update and MCP work.
- [x] 1.3 Ensure prompt bottom toolbar reads the latest startup state on each
  prompt render without direct background terminal writes.
- [x] 1.4 Add focused tests for pending footer segments and completed MCP count
  footer updates.

## 2. Background Version Check

- [x] 2.1 Move startup version update checking out of the pre-welcome blocking
  path.
- [x] 2.2 Record version-check completion in startup state, including no-update,
  failure, and update-available results.
- [x] 2.3 Show update availability in welcome when the check completes before
  prompt input starts.
- [x] 2.4 Show one prompt-toolkit-safe short update notification when the check
  completes after prompt input starts.
- [x] 2.5 Add tests for both pre-prompt welcome update display and post-prompt
  notification behavior.

## 3. Background MCP Startup

- [x] 3.1 Move MCP connection out of the pre-welcome blocking path.
- [x] 3.2 Keep MCP connect, model turns, and cleanup on one async runtime owner so
  MCP objects are not used across incompatible event loops.
- [x] 3.3 Refresh startup state when MCP connects, is skipped, or fails.
- [x] 3.4 Update `/mcp` and existing footer behavior to work correctly while MCP
  startup is pending or failed.
- [x] 3.5 Add tests that welcome and prompt render before a delayed MCP connect
  completes.

## 4. First-Turn MCP Readiness

- [x] 4.1 Gate the first model turn on MCP readiness when MCP startup is still
  pending.
- [x] 4.2 Show normal runtime progress while waiting for MCP readiness after user
  submission.
- [x] 4.3 Ensure local `!cmd`, slash commands that do not need the model, and exit
  flows do not unnecessarily wait on MCP readiness.
- [x] 4.4 Add tests for prompt submission before MCP readiness and for no-wait
  local/slash flows.

## 5. Validation

- [x] 5.1 Run focused startup, footer, update-check, and MCP tests.
- [x] 5.2 Run `tests/test_terminal_ui.py` or the relevant expanded terminal UI
  suite.
- [x] 5.3 Run `ruff`, `ty`, and OpenSpec validation for the change.
