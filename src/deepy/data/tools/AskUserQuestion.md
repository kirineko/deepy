## AskUserQuestion

Use `AskUserQuestion` only when progress is blocked by missing user intent or a required decision.

Parameters:

- `question`: The concise question to ask the user.

Result:

- Returns the standard tool result JSON.
- Sets `awaitUserResponse` to `true` so the UI can wait for the user's answer.
