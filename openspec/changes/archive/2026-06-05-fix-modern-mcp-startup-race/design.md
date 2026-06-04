## Context

`DeepyMcpRuntime` is shared by both UIs. Its `connect()` sets `self.connected = True`
at the top, before awaiting `MCPServerManager.connect_all()`, and only catches
`Exception` (not `CancelledError`):

```
async def connect(self) -> None:
    if self.connected:
        return
    self.connected = True            # latched before the connection actually happens
    ...
    await self._manager.connect_all()
```

`run_prompt_once` reuses an injected runtime and never re-connects; it only reads
`mcp_runtime.active_servers` when building the agent.

- Classic UI (`terminal.py`) runs `connect()` on a persistent background loop
  (`_AsyncRuntimeWorker.run_forever`) and blocks each turn on `mcp_startup.wait()`
  before calling `run_once`. Connection and turns share one loop, so MCP is always
  ready and never interrupted.
- Modern UI (`app.py`) starts connection with
  `run_worker(self._connect_mcp_runtime(), name="mcp-startup", exclusive=False)` in the
  default worker group, and runs each turn with `@work(exclusive=True)` (`run_model_turn`),
  also in the default group.

Textual's `WorkerManager.add_worker(exclusive=True)` calls
`cancel_group(worker.node, worker.group)`, cancelling every worker that shares the node
and group. The startup worker and the turn worker share both, so submitting a prompt
during startup cancels the in-flight connection.

## Goals / Non-Goals

**Goals:**
- Submitting a prompt during Modern UI startup must not cancel MCP connection.
- An interrupted or failed connection attempt must not permanently disable MCP for the session.
- A Modern UI turn that relies on MCP observes connected servers (parity with Classic UI).

**Non-Goals:**
- No change to MCP config format, transports, audit gating, or tool naming.
- No change to Classic UI behavior.
- No new reconnect/retry UX surface (e.g. a `/mcp reconnect` command) in this change.

## Decisions

**Decision 1: Put the MCP startup worker in a dedicated worker group.**
Start it with a distinct `group` (e.g. `group="mcp-startup"`) so the exclusive
`run_model_turn` worker (default group) no longer cancels it via `cancel_group`.
- Alternative considered: make `run_model_turn` non-exclusive. Rejected: exclusivity is
  intentionally used to prevent overlapping turns; weakening it has broader side effects.

**Decision 2: Make `DeepyMcpRuntime.connect()` retryable.**
Only treat the runtime as connected after `connect_all()` completes (track an in-progress
flag separate from the terminal connected flag, and reset it if the attempt is cancelled
or fails). Re-raise `CancelledError` but leave the runtime in a state where a later
`connect()` can retry. Concurrent callers must coordinate (single-flight) rather than each
flipping a latch.
- Alternative considered: leave `connect()` as-is and only fix the worker group. Rejected:
  the latch is an independent latent bug; any future cancellation path (e.g. fast exit,
  task-group teardown) would reproduce the permanent-failure symptom.

**Decision 3: Gate the first MCP-dependent turn on connection readiness.**
Before `run_model_turn` builds the agent, await the shared runtime's connection (idempotent
once connected). This mirrors Classic UI's `mcp_startup.wait()` and guarantees a prompt
submitted during startup still sees active servers rather than an empty list.
- Alternative considered: only fix worker cancellation and accept that a very-early turn
  may run without MCP that one time. Rejected: the user-visible symptom is "MCP failed to
  load on the first prompt"; readiness gating removes the race outcome, not just the latch.

## Risks / Trade-offs

- [Awaiting readiness could delay the first turn if a server is slow] → Connection already
  has `connect_timeout_seconds`; the wait is bounded by the same timeout, and a failed
  server still degrades to built-in tools per existing `mcp-support` behavior.
- [Single-flight connect adds concurrency state] → Keep it minimal (an `asyncio.Event` /
  in-progress flag guarded for the single app loop); cover with focused tests for the
  cancel-then-retry path.
- [Changing connect-state semantics could affect one-shot `deepy run`] → `run_prompt_once`
  creates and connects its own runtime once and cleans it up; the retryable change is
  backward compatible because the success path still ends in `connected == True`.

## Open Questions

- Should the readiness wait surface a transient "connecting MCP..." status in Modern UI, or
  stay silent until the existing `/mcp` status reflects the result? Default: stay silent and
  rely on `/mcp`, matching current Modern UI behavior.
