## AskUserQuestion

当澄清信息会明显影响结果时，使用此工具暂停执行并询问用户：意图不明确、
范围不清楚、用户偏好会影响实现、存在多个实现路线或高影响取舍、下一步需要
用户批准或决策。

如果用户使用中文提问，问题、选项和说明也优先使用中文；否则匹配用户的语言。
若用户使用中文，visible thinking/reasoning 也必须使用中文，除非用户明确要求其他语言。
通常一次只问一个关键问题。若你推荐某个选项，把它放在第一位并在 label 末尾
标注 `(Recommended)` 或中文等价表达。不要为了低影响细节提问；可以合理假设时
继续推进并简短说明假设。

Agent Skills 可能使用通用说法，例如 ask the user、ask one question at a time、
wait for the user's response、get approval、review 或 confirm before continuing。
在 Deepy 中，除非 skill 明确要求不要使用工具，否则这些等待用户输入的步骤都应通过
`AskUserQuestion` 完成。开放问题也必须提供选项；可加入“自定义回答”/`Custom answer`
作为选项，让用户输入自由文本。

Args: `questions` (non-empty array). Each question needs `question` and non-empty `options`;
each option needs `label` and may include `description`. Use `multiSelect=true` only when
multiple choices are allowed.

Returns standard JSON with `awaitUserResponse=true`, `metadata.kind="ask_user_question"`,
and normalized questions.
