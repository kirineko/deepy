## Why

OpenRouter reasoning models can return plaintext reasoning in
`message.reasoning`, while Deepy's current Chat Completions replay path only
preserves `reasoning_content` for DeepSeek and direct Xiaomi. This leaves
OpenRouter tool follow-up turns without the reasoning context that led to the
tool call, even though OpenRouter documents `reasoning_content` as an alias for
`reasoning`.

## What Changes

- Preserve OpenRouter plaintext reasoning by aliasing `message.reasoning` into
  the existing `reasoning_content` replay path.
- Extend the reasoning replay decision so OpenRouter Chat Completions tool
  follow-ups can include `reasoning_content` when the previous OpenRouter
  response contained reasoning.
- Keep the existing DeepSeek and direct Xiaomi `reasoning_content` behavior
  unchanged.
- Do not implement full `reasoning_details` preservation in this change.
- Add tests for OpenRouter alias extraction and replay without requiring live
  network calls.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `deepseek-provider`: OpenAI-compatible provider construction SHALL preserve
  OpenRouter plaintext reasoning through the existing reasoning-content replay
  mechanism for tool follow-up requests.

## Impact

- Affected code likely includes `src/deepy/llm/provider.py` and provider tests.
- The change should be local to Deepy's Chat Completions model wrapper and the
  existing reasoning replay hook.
- No configuration migration, UI change, dependency change, or request-side
  OpenRouter reasoning mapping change is required.
