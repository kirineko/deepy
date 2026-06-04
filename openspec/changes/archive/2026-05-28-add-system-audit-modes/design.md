## Context

Deepy currently registers built-in tools as OpenAI Agents SDK `FunctionTool`
instances and attaches active MCP servers directly to the SDK agent. Managed text
mutation tools already enforce read freshness, workspace boundaries, symlink
safety, and target-type checks, but the model-facing side-effect boundary is not
user-selectable. MCP tools also execute through SDK MCP primitives without a
Deepy-wide approval policy.

OpenAI Agents SDK provides native human-in-the-loop approval support for
function tools, agent tools, shell/apply-patch tools, and MCP servers. A tool can
declare `needs_approval`, SDK runs surface pending approvals through
`interruptions`, and a paused run can resume from `RunState` after
`approve()`/`reject()`. Local MCP servers accept `require_approval`; hosted MCP
tools have an equivalent approval surface. This change should use that SDK
lifecycle instead of encoding approvals as model-visible `AskUserQuestion`
outputs.

## Goals / Non-Goals

**Goals:**

- Provide explicit `normal`, `auto`, and `yolo` audit modes.
- Gate built-in managed text writes, shell command execution, background task
  termination, and MCP tool calls through a single policy model.
- Preserve streaming output by draining the current stream, resolving
  interruptions, and resuming the same SDK run state.
- Surface approval prompts in the stable terminal UI with enough context for a
  user to approve or reject safely.
- Support `Shift+Tab` audit-mode cycling in the prompt.
- Persist a default audit mode and MCP tool approval overrides in TOML config.
- Keep hard Deepy guardrails active in all modes.

**Non-Goals:**

- Replacing Deepy's existing `Write`, `Update`, or `shell` tools with SDK hosted
  shell/apply-patch tools.
- Introducing a separate plan-only mode.
- Treating model-internal session state such as `todo_write` as a file-system
  text write.
- Building a full MCP side-effect classifier in the first implementation.
- Supporting non-terminal approval UIs beyond the existing stable and
  experimental terminal surfaces.

## Decisions

### Use SDK-native approval interruptions

Deepy SHALL register approval behavior through SDK `needs_approval` and MCP
`require_approval`, then handle `RunResult.interruptions` /
`RunResultStreaming.interruptions` in the runner. The runner SHALL convert the
paused result to `RunState`, collect user decisions, call `state.approve()` or
`state.reject()`, and resume the original top-level run.

Alternative considered: reuse `AskUserQuestion` for approvals. That would be
less invasive, but it makes approvals look like model-authored clarification,
pollutes the model conversation, and bypasses SDK support for nested agent and
MCP approval propagation.

### Model the policy as data, not prompt guidance

Add an `AuditMode` value and an `AuditPolicy` helper that maps action classes to
approval decisions:

- `text_write`: `Write` and `Update`
- `command`: `shell`
- `background_task_control`: `task_stop`
- `mcp_tool`: SDK MCP tool calls

Tool descriptions may mention audit behavior, but enforcement SHALL live in tool
registration and runner approval handling. This keeps approval behavior stable
across model providers and prompts.

Alternative considered: ask the model to request approval before risky actions.
That is insufficient because the model can omit the request and because MCP
tools execute outside Deepy's built-in tool descriptions.

### Keep MCP conservative by default

MCP tools can represent anything from search to repository mutation. Deepy SHALL
therefore treat MCP tools as approval-required in `normal` mode and in `auto`
mode unless the user configures a specific MCP server/tool as safe. `yolo` mode
SHALL pass `require_approval="never"` for MCP servers.

The first implementation should support exact server/tool allow rules rather
than heuristic name-based side-effect classification. Existing preferred MCP web
search detection can inform defaults for display, but it should not silently
become a broad safety classifier.

### Preserve hard guardrails in all modes

Audit mode controls whether a human must approve model-requested side effects.
It does not disable Deepy's existing workspace boundary, symlink escape,
unsupported-target, stale-write, or SDK/runtime failure checks. If a tool would
be denied by a hard guardrail, `yolo` SHALL NOT convert it into an allowed
operation.

Sensitive-file handling should be migrated from model-visible
`approval_required` errors to the same SDK approval surface when possible, but
hard-deny policies remain hard denies.

### Make approval UI compact and explicit

The terminal UI SHALL show:

- current audit mode in the prompt footer/status surfaces;
- a pending approval panel with action kind, tool name, arguments summary, and
  target command/path/server/tool;
- a diff preview for managed text writes when available;
- options to approve once, reject, optionally always allow the same tool for the
  current run, or switch audit mode.

For MCP approvals the panel SHALL include server name and MCP tool name. For
shell approvals the panel SHALL show the exact command and working directory.

### Scope mode changes to the active process first

`Shift+Tab` cycling SHALL update the active runtime mode immediately. Persistent
defaults remain config-driven and can be changed through config/slash-command
surfaces. This avoids surprising writes to config from an accidental key press
while still making mode changes responsive.

## Risks / Trade-offs

- SDK approval behavior differs across SDK versions. -> Pin behavior with tests
  against the project dependency and keep SDK API usage small.
- MCP safe-tool allow rules can be misconfigured. -> Default MCP to approval in
  `normal` and `auto`, require exact server/tool names for auto-approval, and
  show the active policy in status surfaces.
- Resuming streaming runs can duplicate or mis-order terminal output. -> Drain
  stream events before showing approvals and add runner tests around interrupted
  and resumed streams.
- `Shift+Tab` terminal encodings vary by host. -> Bind prompt-toolkit `s-tab`
  in the stable UI and cover common Textual/terminal escape variants for the
  experimental UI where applicable.
- Subagent approvals can be nested. -> Always resume the original top-level
  agent run state, because SDK nested approval interruptions surface on the
  outer run.
