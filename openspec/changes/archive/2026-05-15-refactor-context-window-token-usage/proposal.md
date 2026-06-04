## Why

Deepy currently mixes context pressure, latest request usage, and accumulated API token usage in ways that make the bottom toolbar hard to reason about. Cline's split between "Context Window" as latest request context occupancy and "Token Usage" as accumulated usage gives a clearer model that Deepy can adopt while preserving its existing automatic compaction behavior.

## What Changes

- Reframe "Context Window" as the most recent model request's context occupancy: prompt/input tokens plus completion/output tokens plus cache write/read tokens when available, divided by the configured context window.
- Reframe "Token Usage" as cumulative API consumption across the session or turn, preserving prompt/input, completion/output, cache, reasoning, request count, and total token fields.
- Use latest Context Window used tokens as the primary automatic compaction trigger.
- Add a clear internal boundary between:
  - latest request context usage for display,
  - accumulated token usage for reporting,
  - automatic compaction timing.
- Update terminal UI wording so users can distinguish context window occupancy from accumulated token usage.
- Remove the user-visible `compact ~...` statusline segment.
- No breaking CLI command changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `session-context`: Clarify and extend the token accounting contract so latest request context occupancy drives automatic compaction timing while cumulative token usage remains separate.
- `terminal-ui`: Update context and usage display requirements to show Cline-style Context Window and Token Usage semantics, with only a compact-next hint when applicable.

## Impact

- Affected code will likely include `src/deepy/usage.py`, `src/deepy/sessions/jsonl.py`, `src/deepy/llm/runner.py`, `src/deepy/llm/compaction.py`, and `src/deepy/ui/terminal.py`.
- Tests will likely need updates in `tests/test_terminal_ui.py`, `tests/test_session_manager.py`, `tests/test_compaction.py`, and usage/accounting tests.
- No new runtime dependencies are expected.
- Automatic compaction trigger timing changes from effective session pressure to latest Context Window used tokens when that data is available.
