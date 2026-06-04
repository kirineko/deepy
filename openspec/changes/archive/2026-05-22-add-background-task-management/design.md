## Context

Deepy currently runs model turns through the OpenAI Agents SDK streaming API and renders normalized stream events in the stable Rich/prompt-toolkit UI. Shell commands are synchronous: the `shell` tool and local `!cmd` path wait for process completion, capture output, and then return a single tool result. This is simple, but it is a poor fit for long-running dev servers, file watchers, broad test suites, and commands whose useful state is "still running".

OpenAI Agents SDK already provides useful per-run primitives such as `Runner.run_streamed()`, `RunResultStreaming.cancel()`, session persistence, and stream-event consumption. It does not provide a product-level background task registry, output browser, or shutdown policy. Deepy should keep using the SDK for foreground model turns and add a Deepy-owned background task layer for process lifecycle and UI management.

## Goals / Non-Goals

**Goals:**

- Allow the model to launch selected shell commands in the background without blocking the active AI turn.
- Let users inspect background task state with `/ps` and stop background work with `/stop`.
- Let the model list, inspect, and stop background tasks through explicit task management tools.
- Keep background stdout/stderr out of active thinking and response rendering unless the user or model explicitly requests task output.
- Stop all Deepy-owned background tasks during process exit.
- Keep the first implementation small enough to fit the existing stable terminal UI.

**Non-Goals:**

- Do not build a full-screen task browser in the first version.
- Do not automatically trigger a new AI turn when a background task completes.
- Do not make arbitrary user-created OS processes manageable by Deepy.
- Do not replace the existing foreground shell behavior.
- Do not depend on OpenAI Agents SDK internals for process registry or terminal UI state.

## Decisions

### Deepy-owned BackgroundTaskManager

Add a process-local `BackgroundTaskManager` responsible for registration, process launch, output capture, lookup, stop, and shutdown. Each task has a stable id, command, cwd, start/end timestamps, status, pid when available, exit code/error, and an output log path.

Alternatives considered:

- Use OpenAI Agents SDK run state directly. Rejected because SDK run cancellation is per agent run and does not manage child process registries, output logs, or `/ps` surfaces.
- Keep shell backgrounding as raw shell syntax (`cmd &`). Rejected because Deepy could not reliably list, stop, or clean up those processes.

### Status state machine with one-way terminal transitions

Task status should transition from `running` to one terminal status: `completed`, `failed`, or `stopped`. Late process callbacks must not overwrite a terminal status once settled. A stop request during normal runtime should ask the process to terminate and let the settle path record the final result; shutdown may mark and terminate in batch.

Alternatives considered:

- Immediately mark every stop request as stopped. Rejected for normal `/stop` and `task_stop` because a process can exit naturally while the stop signal is in flight.

### Log-file output capture

Background stdout/stderr should be captured to task-specific log files. Task output inspection returns tail/preview data and points to the full log path in metadata when useful.

Alternatives considered:

- Store output only in memory. Rejected because long-running tasks can produce large output and users need predictable inspection.
- Stream output into the active transcript. Rejected because it violates the requirement that background work not corrupt normal thinking/response display.

### Tool contract

Extend `shell` with an opt-in `run_in_background` boolean, defaulting to `false`. Background launch returns a structured success result containing the task id and basic metadata. Add task tools:

- `task_list`: list running and recent background tasks.
- `task_output`: read recent output, optionally waiting for completion with a timeout.
- `task_stop`: stop one task by id.

The shell tool remains the only command launcher; task tools manage tasks after launch.

Alternatives considered:

- Add separate `background_shell` launcher. Rejected because it duplicates most shell guidance and makes it harder for the model to choose the right launcher.

### Stable UI first: `/ps` and `/stop`

Add `/ps` to show running and recent background tasks in a concise text format. Add `/stop` to stop all running tasks created by the current Deepy process/session. These names match the user's requested UI and align with the common CLI mental model.

Alternatives considered:

- `/tasks` full browser. Deferred because it is larger UI work and not needed to solve the immediate management need.

### Exit cleanup ordering

On interactive exit, Deepy should stop background tasks before closing MCP runtimes and the asyncio runner. This keeps process cleanup inside the live runtime and prevents orphaned child processes.

Alternatives considered:

- Let OS process groups clean up on parent exit. Rejected because process group behavior differs across platforms and detached child processes can leak.

## Risks / Trade-offs

- Process cleanup differs across POSIX and Windows -> Use existing Deepy shell termination helpers as a starting point, cover both platforms with focused tests where possible, and degrade to kill after a short grace period.
- Long output logs can grow indefinitely -> Store logs under Deepy-managed task storage and document/implement retention limits for terminal tasks.
- Background tasks can mutate the project while a foreground AI turn is running -> Keep this explicit in task metadata and avoid automatically feeding background output into the active context.
- Model may overuse background mode for short commands -> Tool descriptions should instruct background mode only for long-running commands, servers, watchers, and tasks the user may inspect later.
- `/stop` can terminate important work -> Print clear stopped task summaries and keep per-task `task_stop` available for narrower control.

## Migration Plan

1. Add the background task manager and tests without changing default foreground shell behavior.
2. Extend shell arguments with `run_in_background=false` default so existing model calls remain compatible.
3. Add task management tools and terminal renderers.
4. Add `/ps` and `/stop` to help output, slash handling, and completion.
5. Wire exit cleanup into stable UI and Textual TUI cleanup paths.
6. Validate with focused tests for non-blocking launch, output isolation, stop behavior, and exit cleanup.

Rollback is straightforward before release: remove the background-only tool parameters/tools and keep the existing foreground shell implementation unchanged.

## Open Questions

- Should background task logs persist across Deepy process restarts, or are they session-local only in the first version?
- Should `/stop` accept an optional task id in addition to stopping all tasks, or should single-task stop remain model/tool-only until a richer UI exists?
