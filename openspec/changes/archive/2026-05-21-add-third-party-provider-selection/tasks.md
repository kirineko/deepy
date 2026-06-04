## 1. Provider Catalog And Configuration

- [x] 1.1 Add provider catalog metadata for DeepSeek, OpenRouter, and Xiaomi, including default base URLs, supported model ids, defaults, and thinking capability.
- [x] 1.2 Extend `ModelConfig` loading with optional `provider`, provider inference from known base URLs, and DeepSeek default behavior for configs without provider.
- [x] 1.3 Update model and thinking validation helpers to validate against the resolved provider instead of a DeepSeek-only catalog.
- [x] 1.4 Update config writing and setup helpers to persist `model.provider`, provider default base URL, selected model, `thinking`, and `reasoning_effort`.
- [x] 1.5 Update targeted model config updates to support provider changes, provider default model fallback, provider default base URL updates, and unrelated setting preservation.

## 2. Provider Request Mapping

- [x] 2.1 Refactor the shared thinking/model settings builder to accept resolved provider capability and emit provider-specific request payloads.
- [x] 2.2 Preserve DeepSeek request mapping for `none`, `high`, and `max`.
- [x] 2.3 Add OpenRouter MiMo mapping with `thinking.type` plus `reasoning_effort="high"` or `"none"`.
- [x] 2.4 Add Xiaomi MiMo mapping with `thinking.type` only and no `reasoning_effort`.
- [x] 2.5 Ensure provider construction uses the selected provider base URL and selected model id for ordinary runs, interactive runs, and `doctor --live`.
- [x] 2.6 Keep DeepSeek balance and session-cost lookups gated to official DeepSeek hosts only.

## 3. Stable CLI And Terminal UI

- [x] 3.1 Add `deepy config init --provider` and update interactive setup/reset to ask provider first, then provider-specific model and thinking choices.
- [x] 3.2 Update stable `/model` interactive picker to select provider, model, and provider-appropriate thinking mode before saving.
- [x] 3.3 Update direct `/model` forms for provider-aware setting, while preserving existing DeepSeek shortcuts.
- [x] 3.4 Update `/model list`, usage errors, help text, status, footer, and welcome rendering to show provider, model, and thinking mode clearly.
- [x] 3.5 Reload in-memory settings after provider/model changes so subsequent turns in the same session use the new provider.

## 4. Experimental Textual TUI

- [x] 4.1 Update Textual startup/status surfaces to show active provider, model, and thinking mode.
- [x] 4.2 Update Textual `/model` surfaces to select provider, provider-specific model, and provider-specific thinking mode.
- [x] 4.3 Update Textual `/reset` form to include provider selection, provider default base URL, provider-specific model choices, and provider-specific thinking choices.
- [x] 4.4 Ensure Textual model/reset cancellations preserve saved and in-memory settings unchanged.

## 5. Tests And Documentation

- [x] 5.1 Add configuration tests for explicit provider, base URL inference, unknown no-provider compatibility, defaults, invalid provider/model rejection, and targeted update preservation.
- [x] 5.2 Add provider payload tests for DeepSeek, OpenRouter MiMo enabled/disabled, and Xiaomi MiMo enabled/disabled.
- [x] 5.3 Add stable terminal UI tests for provider-aware `/model`, setup/reset, list/help/welcome/status rendering, and legacy DeepSeek command compatibility.
- [x] 5.4 Add Textual TUI tests for provider-aware model selection and reset form behavior.
- [x] 5.5 Update README and Chinese README configuration examples for DeepSeek, OpenRouter MiMo, and Xiaomi MiMo.
- [x] 5.6 Run focused tests for settings, provider mapping, stable terminal UI, and Textual TUI, then run `openspec validate add-third-party-provider-selection --type change --strict`.
