## Why

Deepy's tool activity and thinking display are useful but visually inconsistent:
tool names use mixed naming styles, write/edit diff headers look different from
ordinary tool progress, thinking is truncated, and AskUserQuestion is not
prominent enough for ambiguous work. This change improves terminal readability
and model collaboration without changing the underlying tool protocol.

## What Changes

- Normalize user-facing tool labels to one display style while preserving
  existing model-facing tool names and session protocol compatibility.
- Render tool names with one consistent, prominent visual treatment, such as
  bold or a bracketed label, instead of assigning different colors per tool.
- Make write/edit diff preview headers follow the same visual vocabulary as
  other tool activity, so `Wrote` and `Edited` no longer appear as a separate
  status style.
- Display DeepSeek thinking fully when it is flushed to the transcript, while
  keeping live working status concise.
- Add prompt guidance so DeepSeek matches thinking language to the user's latest
  natural language, especially Chinese thinking for Chinese user requests.
- Increase AskUserQuestion usefulness by making tool guidance more direct,
  including a Chinese-first trial prompt, while retaining safeguards against
  unnecessary low-impact questions.
- Improve AskUserQuestion's custom-answer option so `Other` is presented as a
  clear user-facing choice rather than an awkward implicit extra item.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Tool progress, write/edit previews, thinking display, and
  AskUserQuestion prompt display requirements change.
- `tools`: AskUserQuestion model guidance and user-facing custom-answer display
  requirements change.
- `deepseek-provider`: DeepSeek thinking language guidance changes.

## Impact

- Terminal rendering paths for streamed tool calls, tool results, session
  history, diff preview headers, and thinking flush output.
- Tool-display formatting helpers and their tests.
- AskUserQuestion terminal prompt display and answer formatting tests.
- System prompt and AskUserQuestion tool documentation used by DeepSeek.
- No breaking change to tool names, tool JSON results, session storage, or
  OpenAI Agents SDK function-tool registration.
