# Preflight File Mutation Approval

## Summary

Show proposed `Write` and `Update` diffs before the user approves a normal-mode
file mutation, then simplify the approval UI to a decision-only control. The
preflight diff is rendered in the transcript for both Classic UI and Modern UI,
while `yolo` and `auto` behavior remain unchanged.

## Motivation

Deepy currently renders diff previews inside audit approval controls. This makes
approval UI complex, especially in Modern UI, where large previews can interact
badly with focus and scrolling. It also means the user approves file mutations
inside a transient control rather than reviewing a durable transcript artifact.

Moving file mutation diffs into transcript preflight blocks makes normal-mode
review clearer:

- the user sees the exact proposed change before approving;
- the approval picker can stay small and reliable;
- rejected changes remain auditable in transcript history;
- Classic and Modern UI can share the same preflight planner.

## Scope

- Shared preflight planner for `Write` and `Update`.
- Normal-mode file mutation approval preview in Classic UI and Modern UI.
- Transcript rendering for proposed file mutation diffs.
- Decision-only approval UI for file mutation approvals.
- Tests proving preview and execution use the same planned diff.

## Out of Scope

- Changing `auto` or `yolo` audit semantics.
- Adding model-facing dry-run tool arguments.
- Replacing the existing post-execution diff result metadata.
- Broad redesign of non-file approvals such as shell, MCP, or background task
  approval.

## Success Criteria

- In normal mode, `Write` and `Update` approval interruptions produce a proposed
  diff before the user approves or rejects.
- Approving a preflighted mutation executes the same planned change.
- Rejecting a preflighted mutation leaves the proposed diff visible as rejected
  transcript context and does not mutate files.
- Classic UI and Modern UI use shared preflight planning logic.
- `auto` and `yolo` modes keep their current execution behavior.
