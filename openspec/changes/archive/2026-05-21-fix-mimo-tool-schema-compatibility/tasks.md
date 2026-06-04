## 1. Compatibility Detection

- [x] 1.1 Add a small helper that identifies MiMo-compatible model paths for provider `xiaomi` and OpenRouter model ids `xiaomi/mimo-v2.5` and `xiaomi/mimo-v2.5-pro`.
- [x] 1.2 Thread the compatibility decision from resolved settings/provider construction into built-in tool construction without changing tool runtime handlers.

## 2. Tool Schema Transformation

- [x] 2.1 Implement a pure schema transformation that recursively removes nullable properties from `required`, removes `null` from MiMo model-visible optional types, and preserves descriptions, `additionalProperties`, and strict mode.
- [x] 2.2 Apply the transformation only to model-visible built-in tool schemas for MiMo-compatible models.
- [x] 2.3 Ensure omitted optional nullable tool arguments continue to use existing runtime defaults.
- [x] 2.4 Replay Xiaomi direct MiMo `reasoning_content` for thinking-enabled tool follow-up requests without applying that replay to OpenRouter MiMo.

## 3. Tests

- [x] 3.1 Add unit tests for the schema transformation on `read_file` and a nested schema with nullable required fields.
- [x] 3.2 Add agent/tool construction tests proving Xiaomi MiMo and OpenRouter MiMo receive compatible schemas while DeepSeek remains unchanged.
- [x] 3.3 Add a mocked runner or provider test showing `read_file` can be called through standard `tool_calls` after compatibility is applied.
- [x] 3.4 Add provider replay tests proving Xiaomi direct MiMo assistant messages include `reasoning_content` on tool follow-up while OpenRouter MiMo does not.

## 4. Verification

- [x] 4.1 Run focused tests for tool schema construction, provider detection, and runner/provider behavior.
- [x] 4.2 Run `openspec validate fix-mimo-tool-schema-compatibility --type change --strict`.
- [x] 4.3 Optionally re-run live Xiaomi/OpenRouter MiMo smoke tests with user-provided API keys to confirm standard `message.tool_calls` are returned.
- [x] 4.4 Re-run a live Xiaomi MiMo Deepy runner smoke test to confirm reading `AGENTS.md` completes after tool output without a 400 response.
