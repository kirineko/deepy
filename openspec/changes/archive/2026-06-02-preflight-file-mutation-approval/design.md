# Design

## Shared Planner

Introduce a shared file-mutation preflight boundary that can plan `Write` and
`Update` without committing side effects. The planner should reuse the same path
resolution, policy checks, text normalization, stale snapshot checks, and update
planning used by the actual tools.

The planner returns a structured result:

- tool name;
- target summary;
- changed files;
- unified diff;
- metadata needed for rendering;
- blocking error details if the mutation cannot be safely planned.

For `Update`, the existing `_plan_update_file()` logic is the natural core, but
it should be accessed through a safer public/internal preflight method instead
of duplicating argument parsing in UI code.

## Approval Flow

Normal-mode file mutation approval becomes:

```text
SDK approval interruption
  -> Deepy builds PendingApproval
  -> approval resolver computes preflight diff
  -> UI renders proposed diff to transcript/console
  -> UI shows compact Approve/Reject decision
  -> SDK state approve/reject resumes run
  -> approved tool executes normally
```

The tool still executes after approval through the existing SDK tool path. This
preserves SDK lifecycle semantics and hard guardrails.

## Avoiding Preview/Execution Drift

The preflight planner and actual execution should share core planning code. If
the file changes between preflight and execution, existing stale-write checks
must reject the actual tool call rather than silently applying a different diff.

Post-execution rendering may suppress duplicate diffs when the proposed diff and
actual diff match, but the tool result metadata should still contain the actual
diff for session history and recovery.

## Rejection Semantics

Rejected proposed diffs remain visible in the transcript or console output and
are marked as rejected. This is intentional: the transcript records what the
model attempted and what the user declined.

## UI Responsibilities

Classic UI prints the proposed diff before the compact approval picker. Modern
UI appends a proposed diff block to the transcript and then displays a compact
bottom-sheet decision. Neither approval control should own large diff preview
rendering after this change.
