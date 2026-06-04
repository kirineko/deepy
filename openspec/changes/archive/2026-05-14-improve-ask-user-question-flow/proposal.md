## Why

AskUserQuestion currently leaks raw tool arguments into the terminal, cannot handle a second clarification round in the same user turn, and is prompted too conservatively for intent discovery. This makes clarification feel like an internal tool trace instead of a smooth user-facing decision flow.

## What Changes

- Keep AskUserQuestion tool calls and progress summaries concise by hiding raw `questions` JSON from terminal output and history rendering.
- Support repeated AskUserQuestion rounds in a single interactive turn until the model completes, the user declines, or normal interruption/error handling applies.
- Improve the user-facing question prompt so internal synthetic answer messages are not printed as if the user typed them.
- Update model-facing AskUserQuestion guidance so Deepy may proactively clarify intent, scope, preferences, and high-impact decisions, not only when completely blocked.
- Polish terminal question prompts for multi-select and fallback options.
- Add regression coverage for multi-round question handling, hidden AskUserQuestion parameters, and updated prompt/tool guidance.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: Clarification questions must render as a clean terminal interaction, support multiple consecutive rounds, and avoid exposing internal protocol text.
- `tools`: AskUserQuestion guidance and display behavior must encourage appropriate clarification and suppress raw question argument payloads from user-facing progress.

## Impact

- Affected code:
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/message_view.py`
  - `src/deepy/data/tools/AskUserQuestion.md`
  - `src/deepy/prompts/system.py`
  - related tests under `tests/`
- No new runtime dependencies are expected.
- No breaking CLI or tool API changes are expected; the existing `AskUserQuestion` JSON contract remains intact.
