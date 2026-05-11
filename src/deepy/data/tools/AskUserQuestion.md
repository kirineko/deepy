## AskUserQuestion

Use `AskUserQuestion` only when progress is blocked by missing user intent or a required decision.

Parameters:

- `questions`: A non-empty array of question objects.
- Each question object must include `question` and a non-empty `options` array.
- Each option must include `label`; `description` is optional.
- Set `multiSelect` to `true` only when the user may choose more than one option.

Result:

- Returns the standard tool result JSON.
- Sets `awaitUserResponse` to `true` so the UI can wait for the user's answer.
- Includes `metadata.kind = "ask_user_question"` and normalized `metadata.questions`.
