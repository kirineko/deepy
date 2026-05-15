## AskUserQuestion

当澄清信息会明显影响结果时，使用此工具暂停执行并询问用户：意图不明确、
范围不清楚、用户偏好会影响实现、存在多个实现路线或高影响取舍、下一步需要
用户批准或决策。

如果用户使用中文提问，问题、选项和说明也优先使用中文；否则匹配用户的语言。
若用户使用中文，visible thinking/reasoning 也必须使用中文，除非用户明确要求其他语言。
通常一次只问一个关键问题。若你推荐某个选项，把它放在第一位并在 label 末尾
标注 `(Recommended)` 或中文等价表达。不要为了低影响细节提问；可以合理假设时
继续推进并简短说明假设。

Args: `questions` (non-empty array). Each question needs `question` and non-empty `options`;
each option needs `label` and may include `description`. Use `multiSelect=true` only when
multiple choices are allowed.

Returns standard JSON with `awaitUserResponse=true`, `metadata.kind="ask_user_question"`,
and normalized questions.
