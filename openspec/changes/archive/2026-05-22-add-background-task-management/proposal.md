## Why

Long-running commands such as dev servers, watchers, builds, and broad test runs currently block Deepy's normal AI turn until they finish or time out. Deepy needs a first-class background task path so the assistant can continue thinking and responding while users can inspect and stop background work explicitly.

## What Changes

- Add a managed background task runtime for shell-like work with task ids, status, output capture, stop requests, and exit cleanup.
- Extend the model-facing shell capability so commands can opt into background execution and immediately return a task id instead of blocking the active AI turn.
- Add model-facing task management tools for listing tasks, reading output, and stopping tasks.
- Add stable terminal UI commands:
  - `/ps` lists running and recent background tasks with concise status and recent output hints.
  - `/stop` stops all running background tasks for the current Deepy process/session.
- Ensure background task output never streams into the active assistant thinking or response transcript unless explicitly requested through task output inspection.
- Ensure Deepy shuts down all running background tasks on user exit before closing MCP runtimes and the event loop.

## Capabilities

### New Capabilities

- `background-tasks`: Managed lifecycle, output capture, status, stop, and cleanup behavior for Deepy-owned background work.

### Modified Capabilities

- `tools`: Extend shell execution and add task management tools that expose background task control to the model.
- `terminal-ui`: Add `/ps` and `/stop` user-facing management commands and background task status behavior.
- `experimental-textual-tui`: Preserve clean exit and non-interference behavior when background tasks exist in the opt-in Textual UI.

## Impact

- Affects `src/deepy/tools/builtin.py`, `src/deepy/tools/agents.py`, tool docs, tool output rendering, and tests for shell/task tools.
- Affects the stable Rich/prompt-toolkit interactive UI in `src/deepy/ui/terminal.py`, slash command help/completion, status footer text, and exit cleanup.
- Affects the experimental Textual TUI cleanup path and command unsupported/supported handling.
- Adds a Deepy-owned task manager module and persistent or temporary output-log handling for background task stdout/stderr.
- Requires tests for non-blocking background launch, task listing/output/stop, output isolation, process cleanup, and cross-platform termination behavior.
