## Context
Subagents share a ToolRuntime so audit, read state, background work and search limits remain coordinated.

## Goals / Non-Goals
Use each agent's effective model for Read image validation. Do not clone or mutate the shared runtime or change tool schemas.

## Decisions
Pass an optional ModelConfig through the Read tool binding and into both single and batch reads. Resolve the effective child config once while constructing subagents. Other tools continue to use the original shared runtime.

## Risks / Trade-offs
The optional model is an internal argument, never exposed in the model-facing tool schema. Concurrency tests protect against temporary shared-setting mutation.

The existing large tools/agents.py module receives only a small Read argument-binding change. Keeping the capability check in the focused Read runtime avoids an unrelated tool-factory refactor.
