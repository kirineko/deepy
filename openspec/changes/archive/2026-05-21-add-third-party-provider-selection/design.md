## Context

Deepy currently has a DeepSeek-first model configuration:
`model.name`, `model.base_url`, `model.api_key`, `model.thinking`, and
`model.reasoning_effort`. The stable UI, Textual TUI, setup/reset flows, status,
and provider settings all assume the supported model catalog is DeepSeek-only.

The next provider surface must support MiMo through two routes and allow
advanced OpenRouter users to paste other OpenRouter model ids during
initialization/reset:

- OpenRouter: `https://openrouter.ai/api/v1`, with model ids
  `xiaomi/mimo-v2.5-pro` and `xiaomi/mimo-v2.5`.
- Xiaomi official API: `https://api.xiaomimimo.com/v1`, with model ids
  `mimo-v2.5-pro` and `mimo-v2.5`.

The relevant thinking parameter shape shared by Xiaomi-style APIs is
`extra_body={"thinking": {"type": "enabled"|"disabled"}}`. MiMo should be
treated as switch-only in Xiaomi's UI: users choose enabled or disabled, not an
effort strength. OpenRouter uses the OpenRouter `reasoning` object. Most
OpenRouter models can use boolean `reasoning.enabled`; models that support
effort can additionally receive `reasoning.effort`.

## Goals / Non-Goals

**Goals:**

- Make `deepseek`, `openrouter`, and `xiaomi` explicit provider choices for new
  setup/reset and model-selection flows.
- Keep DeepSeek as the default provider and preserve existing configs that have
  no `model.provider`.
- Infer provider from known base URLs when possible, including DeepSeek,
  OpenRouter, and Xiaomi.
- Keep unknown old custom `base_url` configs running with the current
  DeepSeek-style behavior instead of introducing a separate user-visible
  compatibility provider.
- Expose only supported models in `/model` UI:
  - DeepSeek: `deepseek-v4-pro`, `deepseek-v4-flash`
  - OpenRouter: `xiaomi/mimo-v2.5-pro`, `xiaomi/mimo-v2.5`
  - Xiaomi: `mimo-v2.5-pro`, `mimo-v2.5`
- Allow OpenRouter setup/reset/init to use a custom model id copied from
  OpenRouter, with correctness left to the user.
- Expose provider-appropriate thinking choices:
  - DeepSeek: `none`, `high`, `max`
  - OpenRouter: `enabled`, `disabled`, `xhigh`, `high`, `medium`, `low`,
    `minimal`, `none`
  - Xiaomi MiMo: `disabled`, `enabled`
- Centralize request payload mapping so the UI writes normalized settings while
  provider-specific wire details stay in the model-settings builder.

**Non-Goals:**

- Supporting arbitrary OpenRouter or Xiaomi models beyond the listed MiMo ids.
- Adding Kimi to the UI in this change.
- Adding per-provider pricing, quota, or balance support beyond existing
  DeepSeek balance behavior.
- Replacing the OpenAI Agents SDK provider boundary.
- Migrating old configs in-place before the user saves new provider settings.

## Decisions

1. Add a provider catalog as the source of truth.

   A small built-in catalog should define:

   - provider id, label, default base URL, and optional API key guidance URL
   - provider model ids, labels, and descriptions
   - thinking capability: `deepseek-effort` or `switch-only`
   - default model and default thinking choice

   This prevents UI, config validation, help text, and request mapping from
   carrying separate hard-coded provider/model lists.

   Alternative considered: keep `DEEPSEEK_MODEL_CATALOG` and add ad hoc checks
   for MiMo in each UI path. That would keep the immediate diff smaller but
   would make setup/reset, stable `/model`, Textual `/model`, and payload
   mapping drift-prone.

2. Persist `model.provider` only when saving new provider-aware settings.

   New or reset configs should include:

   ```toml
   [model]
   provider = "openrouter"
   name = "xiaomi/mimo-v2.5-pro"
   base_url = "https://openrouter.ai/api/v1"
   thinking = true
   reasoning_effort = "high"
   ```

   Existing configs without `provider` remain valid. Loading should resolve a
   provider in this order:

   1. explicit `model.provider` if valid
   2. known `model.base_url` host
   3. DeepSeek default behavior

   Unknown custom base URLs with no provider must not become a new user-visible
   provider. They should keep the existing DeepSeek-style request mapping to
   avoid breaking current users who manually set `base_url`.

   Alternative considered: require provider for all configs. That would be a
   migration break for current users and is unnecessary because old settings
   already contain enough information to keep running.

3. Keep `reasoning_effort` as a persisted compatibility field.

   For switch-only MiMo providers, saving `enabled` should write
   `thinking = true` and `reasoning_effort = "high"`; saving `disabled` should
   write `thinking = false` and `reasoning_effort = "none"`.

   The field remains useful as a normalized state marker and is required for
   OpenRouter disabled behavior, but direct Xiaomi request construction should
   not send `reasoning_effort` because Xiaomi's documented control is
   `thinking.type`.

   Alternative considered: add a new `model.thinking_mode = "enabled"` field.
   That better matches the switch-only UI but would create yet another config
   representation. Reusing `thinking` plus `reasoning_effort` keeps the file
   compatible with existing code paths and tests.

4. Split user-facing thinking choices from wire payload values.

   DeepSeek continues to expose and send:

   - `none` -> `thinking.type=disabled`, no `reasoning_effort`
   - `high` -> `thinking.type=enabled`, `reasoning_effort="high"`
   - `max` -> `thinking.type=enabled`, `reasoning_effort="max"`

   Xiaomi exposes:

   - `disabled`
   - `enabled`

   OpenRouter exposes:

   - `xhigh`
   - `high`
   - `medium`
   - `low`
   - `minimal`
   - `none`

   Wire mapping:

   - Xiaomi enabled -> `extra_body={"thinking": {"type": "enabled"}}`
   - Xiaomi disabled -> `extra_body={"thinking": {"type": "disabled"}}`
   - OpenRouter enabled -> `extra_body={"reasoning": {"enabled": true}}`
   - OpenRouter disabled/none -> `extra_body={"reasoning": {"enabled": false}}`
   - OpenRouter effort -> `extra_body={"reasoning": {"enabled": true, "effort": "<selected effort>"}}`

   This keeps OpenRouter's OpenRouter-native reasoning mapping separate from
   Xiaomi's official OpenAI-compatible API.

5. Make setup/reset and `/model` provider-first.

   Interactive setup/reset should ask for provider before model, then choose a
   provider-specific default base URL and provider-specific model list. Users
   may still override base URL manually. When the provider is OpenRouter,
   setup/reset should also allow the user to paste any model id copied from the
   OpenRouter model page and select an OpenRouter reasoning effort. The user is
   responsible for ensuring the custom OpenRouter model id and effort are
   accepted by OpenRouter.

   The stable `/model` flow should become:

   ```text
   Select provider -> Select model -> Select thinking
   ```

   Direct command forms should support provider-aware explicit use, for example:

   ```text
   /model set openrouter xiaomi/mimo-v2.5-pro high
   /model set xiaomi mimo-v2.5-pro disabled
   /model provider deepseek
   /model thinking enabled
   ```

   The exact parser can also preserve old forms for DeepSeek:

   ```text
   /model set deepseek-v4-flash high
   /model reasoning max
   ```

   When a user changes provider without specifying a model, Deepy should select
   that provider's default model and default thinking choice rather than trying
   to keep an incompatible old model id.

6. Keep input suggestions non-thinking for the active provider.

   DeepSeek should keep using fixed `deepseek-v4-flash` with thinking disabled.
   Third-party providers should use the active configured provider/model with
   thinking disabled. For OpenRouter custom models, that means the configured
   model id plus `reasoning.enabled=false`.

## Risks / Trade-offs

- [Risk] Unknown old custom `base_url` users may expect arbitrary model ids to
  remain valid. -> Mitigation: do not require `provider`, and keep unknown
  provider resolution on the existing DeepSeek-style behavior unless the user
  explicitly selects a known provider.
- [Risk] OpenRouter and Xiaomi direct APIs have similar thinking switches but
  different behavior around `reasoning_effort`. -> Mitigation: centralize
  provider-aware payload mapping and test each provider's expected request body.
- [Risk] Adding provider-first UI increases setup steps for new DeepSeek users.
  -> Mitigation: keep DeepSeek first and default, and prefill DeepSeek model and
  base URL values.
- [Risk] Existing `/model` tests and user muscle memory use `none/high/max`.
  -> Mitigation: preserve DeepSeek old direct forms while adding provider-aware
  forms for third-party providers.
- [Risk] Balance/status code is DeepSeek-specific. -> Mitigation: keep balance
  lookups gated to official DeepSeek hosts and display third-party providers
  without attempting balance calls.

## Migration Plan

1. Introduce provider/model/thinking catalog types and defaults.
2. Extend config loading to read optional `model.provider` and infer provider
   from known base URLs.
3. Extend config writing and targeted updates to persist provider, model,
   base_url, thinking, and reasoning effort without dropping unrelated sections.
4. Replace DeepSeek-only validation in setup/reset and model commands with
   provider-aware validation.
5. Update the shared model-settings builder with provider-aware thinking
   payload mapping.
6. Update stable UI, Textual TUI, welcome/status/help, and docs.
7. Add focused tests for loading, saving, UI command handling, and request
   payloads.

Rollback is straightforward because old configs without `model.provider` remain
valid and new configs still use existing `[model]` keys. If needed, users can
remove `model.provider` and set DeepSeek-compatible `name`, `base_url`,
`thinking`, and `reasoning_effort` manually.

## Open Questions

- Whether direct `/model thinking enabled` should be accepted as an alias for
  DeepSeek `high`, or rejected for DeepSeek to keep effort semantics explicit.
