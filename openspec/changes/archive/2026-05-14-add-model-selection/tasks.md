## 1. Model Catalog And Configuration

- [x] 1.1 Add a centralized DeepSeek model catalog for `deepseek-v4-pro` and `deepseek-v4-flash`, including picker labels, descriptions, and allowed reasoning modes.
- [x] 1.2 Add reasoning-mode normalization for `none`, `high`, and `max` while using existing `thinking` and `reasoning_effort` config fields as the persistence format.
- [x] 1.3 Update config parsing so missing reasoning settings default to `max` and legacy `thinking = false` resolves to `none`.
- [x] 1.4 Add targeted config update helpers for `model.name`, `model.thinking`, and `model.reasoning_effort` that preserve unrelated TOML fields and `0600` permissions.
- [x] 1.5 Add config tests for default model, supported models, invalid command-selected models, existing thinking fields, and targeted update preservation.

## 2. Provider Mapping

- [x] 2.1 Update `build_thinking_extra_body` and `build_model_settings` to map reasoning mode `none` to disabled thinking without `reasoning_effort`.
- [x] 2.2 Update provider construction tests to assert the selected model name is passed to `OpenAIChatCompletionsModel`.
- [x] 2.3 Add model-settings tests for `none`, `high`, and `max` request bodies.
- [x] 2.4 Verify live doctor and ordinary run paths still use the shared provider/model-settings construction path.

## 3. Interactive `/model` Command

- [x] 3.1 Add `/model` to built-in slash command completion and help output.
- [x] 3.2 Implement `/model list` to show supported models and reasoning modes.
- [x] 3.3 Implement direct `/model set <model>` and `/model reasoning <none|high|max>` command forms with validation and no config changes on invalid input.
- [x] 3.4 Implement the no-argument `/model` picker flow: show current settings, select model, then select reasoning mode.
- [x] 3.5 Ensure cancellation at either picker step leaves persisted and in-memory model settings unchanged.
- [x] 3.6 Reload settings after a successful `/model` change so subsequent turns in the same interactive process use the new model settings.
- [x] 3.7 Print concise confirmation after successful changes, including selected model and reasoning mode.
- [x] 3.8 Add terminal UI tests for picker success, picker cancellation, direct commands, invalid commands, help output, and slash completion.

## 4. User-Facing Status And Documentation

- [x] 4.1 Update welcome/status rendering to show the active model and unified reasoning mode clearly.
- [x] 4.2 Update README and README.zh-CN configuration examples to document supported models and `none|high|max` reasoning mode.
- [x] 4.3 Update setup/config documentation to show existing `[model] name`, `thinking`, and `reasoning_effort` fields as the persisted format.
- [x] 4.4 Add or update tests for welcome/status text that currently expects separate thinking and reasoning values.

## 5. Verification

- [x] 5.1 Run focused tests for config, provider, terminal UI, welcome, status, and CLI command behavior.
- [x] 5.2 Run the full `uv run pytest` suite.
- [x] 5.3 Run `uv run ruff check`.
- [x] 5.4 Run `uv run pyright`.
- [x] 5.5 Run OpenSpec validation for `add-model-selection`.
