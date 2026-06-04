## Context

The stable terminal UI currently performs two potentially slow startup tasks
before the welcome panel is printed:

- a synchronous version update check against PyPI
- an awaited MCP connection through `DeepyMcpRuntime.connect()`

This means slow network access, unavailable PyPI, or slow MCP server startup can
delay the first visible UI. The user-facing goal is to make Deepy feel alive
immediately: show the welcome panel quickly, let the prompt become usable, and
surface update/MCP progress through the existing terminal UI instead of blocking
before the first screen.

The key constraint is terminal ownership. Once prompt-toolkit is reading input,
background Rich prints can corrupt the input row or bottom toolbar. Startup
updates must therefore use prompt-toolkit-safe rendering primitives or update
state consumed by the prompt toolbar.

## Goals / Non-Goals

**Goals:**

- Print the stable UI welcome panel without waiting for version update checks or
  MCP connection.
- Make the prompt available immediately after welcome.
- Show startup progress as ghost-style footer state while update checks or MCP
  connection are pending.
- Notify the user about available updates without corrupting prompt input.
- Preserve stable tool availability by waiting for MCP readiness before the
  first model turn starts.
- Keep MCP connection, model turns, and MCP cleanup on one async runtime boundary.
- Keep the behavior testable without requiring live network or real MCP servers.

**Non-Goals:**

- Do not change MCP server configuration, policy, or tool naming.
- Do not change provider/model selection, prompt syntax, or slash-command names.
- Do not add realtime final-answer streaming.
- Do not implement automatic terminal background color detection.
- Do not change the experimental Textual TUI startup path unless shared config or
  tests require minor alignment.

## Decisions

### Render welcome before startup I/O completes

The stable UI should build and print the welcome panel after local settings,
theme, skills, and prompt session setup are available, but before network update
checks or MCP server connection complete.

Rationale: local work is fast and deterministic; network and MCP startup are the
variable operations. Moving only the variable work behind first render maximizes
perceived responsiveness without changing user-visible command behavior.

Alternative considered: keep waiting for MCP but move only version checks into
the background. This improves PyPI failures but still leaves slow MCP servers
blocking first paint, which is the larger startup risk.

### Use a startup state object for footer and notification updates

Introduce a small startup state owned by the stable terminal UI. It should track:

- update check state: pending, unavailable, available update, or complete
- MCP state: pending, connected, skipped, or failed
- whether prompt input has started

The prompt bottom toolbar should be built from this state each time prompt input
is requested. Pending states should appear as concise ghost-style segments such
as `update checking` and `mcp connecting`. Connected MCP should continue using
the existing `mcp N` segment.

Rationale: the footer already belongs to prompt-toolkit during input, so using it
for startup progress keeps ownership consistent.

Alternative considered: print transient Rich status lines while startup work is
running. That would be consistent with model runtime status, but startup work can
complete while prompt-toolkit owns the terminal, so direct prints are unsafe.

### Use prompt-toolkit-safe update notifications

If a newer version is discovered before prompt input starts, the welcome state can
include it before the first prompt. If the update is discovered after prompt input
has started, show one short notification through
`prompt_toolkit.application.run_in_terminal()` instead of redrawing the full
welcome panel.

Rationale: `run_in_terminal()` coordinates with prompt-toolkit's active
application. It can print a concise notification without corrupting the prompt.
Reprinting the full welcome after input starts would push the transcript and
feel like a large unsolicited output block rather than an in-place refresh.

Alternative considered: always redraw welcome when an update is found. This is
acceptable only before prompt input begins; after that it is visually disruptive
and risks terminal state conflicts.

### Keep MCP and model execution on one async runtime boundary

MCP connection should run asynchronously without blocking the initial prompt, but
the connected MCP runtime must be used on the same async runtime boundary as
model turns and cleanup.

A practical shape is an async runtime thread or equivalent owner that handles:

- `mcp_runtime.connect()`
- waiting for MCP readiness before the first model turn
- `run_prompt_once()`
- `mcp_runtime.cleanup()`

The main thread can keep terminal prompting responsive while dispatching async
work to this owner.

Rationale: MCP session/server objects can be tied to the event loop that created
them. Connecting in one loop and using or cleaning up in another loop is risky.

Alternative considered: launch MCP connection in a simple background thread with
`asyncio.run()`. This is easier to wire, but it can create cross-event-loop MCP
objects that later model turns cannot safely use.

### Wait for MCP before the first model turn

If the user submits a model prompt before MCP connection completes, Deepy should
wait for MCP readiness before invoking the model. During that wait, the terminal
should show a normal runtime status such as the existing elapsed-time status with
an MCP-connecting detail.

Rationale: users can type immediately, but the first model turn still sees the
complete configured tool set. This avoids the surprising behavior where MCP
tools become available only on the second turn.

Alternative considered: let the first turn run without MCP if MCP is still
connecting. This feels faster in edge cases, but changes available tools based
on timing and makes behavior harder to explain.

## Risks / Trade-offs

- Background startup state races with prompt input -> Use a lock-protected state
  object and update the prompt-toolbar data model, not raw terminal output.
- MCP connect never finishes or hangs -> Keep the existing MCP connection
  timeout semantics and expose failure/skipped state in the footer or `/mcp`.
- First prompt appears usable but waits on MCP after submit -> Show a clear
  runtime status while waiting so the post-submit pause is attributable.
- `run_in_terminal()` is async -> Schedule it through prompt-toolkit's active
  application or a compatible async bridge; tests should cover the fallback when
  no prompt app is active.
- Redrawing welcome after prompt starts is disruptive -> Only allow full welcome
  refresh before prompt input starts; use short notifications afterward.

## Migration Plan

This is an internal startup behavior change with no configuration migration.
Existing MCP configuration and update-check settings continue to work. Rollback
is straightforward: return update checks and MCP connection to the pre-welcome
synchronous startup path.
