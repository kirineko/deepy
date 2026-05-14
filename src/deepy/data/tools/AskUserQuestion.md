## AskUserQuestion

Ask the user when clarification would materially improve the result: ambiguous intent,
unclear scope, user preferences, high-impact trade-offs, or required approval. Do not
ask for low-impact details when a reasonable assumption can keep progress moving.

Args: `questions` (non-empty array). Each question needs `question` and non-empty `options`;
each option needs `label` and may include `description`. Use `multiSelect=true` only when
multiple choices are allowed.

Returns standard JSON with `awaitUserResponse=true`, `metadata.kind="ask_user_question"`,
and normalized questions.
