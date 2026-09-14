## Why
Subagent model overrides currently leave Read image checks bound to the parent model. This rejects supported images or returns images that the child cannot consume.

## What Changes
- Bind Read capability validation to the effective child model without mutating shared runtime state.
- Cover both override directions, inherited models, batch reads, and concurrent parent/child calls.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `subagents`: Read uses the effective subagent model capabilities.

## Impact
Subagent construction, built-in Read bindings, tests and bilingual documentation.
