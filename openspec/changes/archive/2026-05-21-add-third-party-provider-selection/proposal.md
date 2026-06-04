## Why

Deepy currently assumes a DeepSeek-first configuration surface even though users
now want to run MiMo models through either OpenRouter or Xiaomi's official
OpenAI-compatible API. Users should be able to choose a supported provider and
model from setup, reset, and model-selection UI without hand-editing TOML or
learning each platform's thinking parameter quirks.

## What Changes

- Add a user-facing provider catalog with `deepseek`, `openrouter`, and
  `xiaomi`; DeepSeek remains the default for new and legacy configurations.
- Add provider-specific model catalogs:
  - DeepSeek: existing `deepseek-v4-pro` and `deepseek-v4-flash`.
  - OpenRouter: `xiaomi/mimo-v2.5-pro` and `xiaomi/mimo-v2.5`.
  - Xiaomi: `mimo-v2.5-pro` and `mimo-v2.5`.
- Persist an optional `model.provider` field in TOML for newly saved provider
  selections while continuing to load configs that do not have the field.
- Resolve missing `model.provider` from known `base_url` values when possible;
  otherwise keep the current DeepSeek-style behavior for backward compatibility.
- Update interactive setup, reset, `/model`, status, welcome, and help surfaces
  so the active provider, model, and thinking mode are visible.
- For OpenRouter initialization/reset, allow users to paste a custom model id
  from the OpenRouter model page and select either boolean reasoning
  `enabled`/`disabled` or an OpenRouter effort value.
- Map OpenRouter reasoning to `reasoning.enabled` by default and add
  `reasoning.effort` only when the user explicitly selects an effort value.
- Map Xiaomi MiMo thinking choices to `thinking.type=enabled|disabled`.
- Keep DeepSeek's existing `none`, `high`, and `max` reasoning modes and
  DeepSeek thinking payload behavior unchanged.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `configuration`: persistent TOML settings gain optional provider selection,
  provider inference from known base URLs, provider-specific model validation,
  and switch-only thinking semantics for MiMo providers.
- `deepseek-provider`: the shared OpenAI-compatible provider path gains
  provider-aware request settings for DeepSeek, OpenRouter MiMo, and Xiaomi
  MiMo while preserving the current DeepSeek default path.
- `terminal-ui`: stable setup/reset/model-selection UI exposes provider,
  provider-specific model choices, and provider-appropriate thinking controls.
- `experimental-textual-tui`: Textual reset and model-selection surfaces expose
  the same provider, model, and thinking choices as the stable terminal UI.

## Impact

- Affected code:
  - `src/deepy/config/settings.py`
  - `src/deepy/llm/thinking.py`
  - `src/deepy/llm/provider.py`
  - `src/deepy/cli.py`
  - `src/deepy/status.py`
  - `src/deepy/ui/model_picker.py`
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/welcome.py`
  - `src/deepy/tui/app.py`
  - `src/deepy/tui/screens.py` or related reset/model form surfaces
- Affected tests:
  - configuration loading, provider inference, and targeted update tests
  - provider/model-settings payload tests for DeepSeek, OpenRouter MiMo, and
    Xiaomi MiMo
  - stable `/model`, `/reset`, welcome, status, and help rendering tests
  - Textual TUI model/reset form tests
- Documentation impact:
  - README config examples and setup guidance should mention DeepSeek,
    OpenRouter, and Xiaomi provider choices with the supported model IDs.
- No new runtime dependency is expected.
