## 1. Terminal Clarification Loop

- [x] 1.1 Refactor the interactive terminal turn handling so `waiting_for_user` summaries are processed in a loop instead of a single follow-up run.
- [x] 1.2 Preserve the active `session_id` across every AskUserQuestion continuation in the loop.
- [x] 1.3 Add a defensive maximum clarification-round limit and a concise terminal message when the limit is reached.
- [x] 1.4 Ensure the final assistant output and usage footer are printed from the last completed continuation.

## 2. AskUserQuestion Display Polish

- [x] 2.1 Hide raw AskUserQuestion `questions` arguments in streamed tool-call summaries.
- [x] 2.2 Hide raw AskUserQuestion `questions` arguments when rendering session history.
- [x] 2.3 Stop printing the internal formatted answer protocol as a normal user input line.
- [x] 2.4 Improve question prompts so multi-select questions explain comma-separated selection.
- [x] 2.5 Review the fallback custom-answer option label and prompt text for readability in Chinese and English terminal flows.

## 3. Model Guidance

- [x] 3.1 Update AskUserQuestion tool documentation to describe proactive clarification for ambiguous intent, scope, preferences, and high-impact choices.
- [x] 3.2 Update system prompt guidance so asking is permitted when clarification materially improves the outcome, while still discouraging low-impact questions.
- [x] 3.3 Keep the existing AskUserQuestion argument and result JSON contract unchanged.

## 4. Tests

- [x] 4.1 Add terminal UI tests covering multiple consecutive `waiting_for_user` rounds in one interactive turn.
- [x] 4.2 Add message-view or terminal-rendering tests proving AskUserQuestion call summaries do not include raw `questions` JSON.
- [x] 4.3 Add prompt/tool documentation tests covering the revised clarification guidance.
- [x] 4.4 Run the focused test files for runner, terminal UI, message rendering, prompt docs, and AskUserQuestion behavior.
