## Why

MiMo models served through Xiaomi official API and OpenRouter can return valid
OpenAI `tool_calls`, but they fail when Deepy exposes tools whose schemas mark
nullable optional arguments as required. In Deepy this makes file-reading turns
such as "read AGENTS.md" end with only a short thinking segment and no executed
tool.

## What Changes

- Add a MiMo-specific compatibility layer for model-visible function tool
  schemas.
- For Xiaomi MiMo and OpenRouter-hosted MiMo models, expose optional nullable
  tool parameters as optional instead of `required + nullable`.
- Preserve Deepy's internal tool runtime behavior and existing argument
  defaults.
- Replay Xiaomi direct MiMo `reasoning_content` during thinking-enabled
  multi-turn tool follow-ups, as required by Xiaomi's API.
- Preserve the current strict schema behavior for DeepSeek and other providers.
- Add tests that prove MiMo-compatible schemas produce standard OpenAI
  `tool_calls` for `read_file`-style tools and that non-MiMo providers are
  unchanged.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tools`: Provider/model-compatible built-in tool schemas for MiMo while
  preserving the existing tool set and runtime behavior.
- `deepseek-provider`: OpenAI-compatible provider construction SHALL apply MiMo
  tool schema compatibility only for Xiaomi MiMo and OpenRouter MiMo models.

## Impact

- Affected code likely includes `src/deepy/tools/agents.py`,
  `src/deepy/llm/agent.py`, and provider/model catalog helpers in
  `src/deepy/config/settings.py` or adjacent provider utilities.
- Tests should cover schema transformation, agent construction, and a minimal
  model-call path with mocked Agents SDK tools.
- No user-facing configuration migration is required.
