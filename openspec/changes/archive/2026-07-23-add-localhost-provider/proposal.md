## Why

Users run CLIProxyAPI locally as an OpenAI-compatible gateway for GPT-5.6 models
(`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`). Deepy currently only exposes
DeepSeek, OpenRouter, and Xiaomi providers over Chat Completions, so those local
GPT-5.6 models cannot be selected or used with Responses API reasoning effort
and image input.

## What Changes

- Add a user-facing `localhost` provider with default base URL
  `http://127.0.0.1:8317/v1`.
- Add localhost model catalog: `gpt-5.6-sol`, `gpt-5.6-terra` (default),
  `gpt-5.6-luna`, all marked as supporting image input.
- Add localhost thinking modes: `none`, `low`, `medium` (default), `high`,
  `xhigh`.
- Construct localhost main-conversation providers with OpenAI Agents SDK
  `OpenAIResponsesModel` instead of Chat Completions.
- Map localhost reasoning effort through Responses API `reasoning.effort`
  (not DeepSeek/OpenRouter/Xiaomi chat `extra_body` shapes).
- Keep API key configuration in `~/.deepy/config.toml` `[model] api_key`
  (same as other providers; overridable by `DEEPY_API_KEY`).
- Use `gpt-5.6-luna` with reasoning effort `none` for localhost input
  suggestions over Chat Completions.
- Infer provider `localhost` from `127.0.0.1` / `localhost` base URL hosts.
- Note: local CLIProxyAPI may normalize Responses `reasoning.effort=none` to
  `low` on the wire; Deepy still exposes and persists `none` as the user-facing
  disabled-thinking choice.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `configuration`: provider catalog, base URL defaults/inference, thinking-mode
  persistence, and image-input model capability metadata gain `localhost`.
- `deepseek-provider`: OpenAI Agents SDK provider construction gains a Responses
  API branch for localhost; model settings and input-suggestion settings gain
  localhost mappings.
- `image-understanding-input`: supported image model set includes localhost
  GPT-5.6 models.

## Impact

- Affected code:
  - `src/deepy/config/providers.py`
  - `src/deepy/config/schema.py`
  - `src/deepy/config/config_io.py`
  - `src/deepy/config/settings.py`
  - `src/deepy/config/__init__.py`
  - `src/deepy/llm/provider.py`
  - `src/deepy/llm/thinking.py`
  - `src/deepy/llm/multimodal.py`
  - `src/deepy/input_suggestions.py`
  - `src/deepy/ui/shared/model_picker.py`
  - `src/deepy/cli.py`
- Affected tests: config loading/inference, provider bundle/model settings,
  multimodal support, input suggestions, picker/CLI help text.
- No new runtime dependency; existing `openai` / `openai-agents` already support
  Responses models and `reasoning.effort` values including `none` and `xhigh`.
