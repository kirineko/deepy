## AskUserQuestion

Ask the user only when progress is blocked by missing intent or a required decision.

Args: `questions` (non-empty array). Each question needs `question` and non-empty `options`;
each option needs `label` and may include `description`. Use `multiSelect=true` only when
multiple choices are allowed.

Returns standard JSON with `awaitUserResponse=true`, `metadata.kind="ask_user_question"`,
and normalized questions.
