## 1. OpenRouter Alias Bridge

- [x] 1.1 Add a small helper that detects OpenRouter Chat Completions contexts from the resolved base URL or provider-equivalent request context.
- [x] 1.2 Before Chat Completions responses are converted into SDK output items, copy a non-empty OpenRouter `message.reasoning` string into `message.reasoning_content` only when `reasoning_content` is absent.
- [x] 1.3 Preserve existing `reasoning_content` values and leave `reasoning_details` unmodified.

## 2. Replay Hook

- [x] 2.1 Extend the existing reasoning-content replay hook to allow OpenRouter-origin reasoning items for OpenRouter follow-up requests.
- [x] 2.2 Keep DeepSeek and direct Xiaomi MiMo replay behavior unchanged.
- [x] 2.3 Ensure non-OpenRouter third-party providers do not receive OpenRouter-specific alias replay.

## 3. Tests

- [x] 3.1 Add unit tests proving OpenRouter `reasoning` is aliased into `reasoning_content` before SDK output item conversion.
- [x] 3.2 Add provider replay tests proving OpenRouter tool-call follow-up messages include `reasoning_content` after aliasing.
- [x] 3.3 Add regression tests proving existing DeepSeek/direct Xiaomi replay behavior remains unchanged and unrelated providers still do not replay.
- [x] 3.4 Add a test proving existing `reasoning_content` is not overwritten and `reasoning_details` is not mutated.

## 4. Verification

- [x] 4.1 Run focused provider/replay tests.
- [x] 4.2 Run `openspec validate add-openrouter-reasoning-alias-replay --type change --strict`.
- [x] 4.3 Optionally re-run a live OpenRouter MiMo smoke test to confirm `message.reasoning` aliases through the existing replay path.
