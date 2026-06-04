## Context

Deepy already has a `ModelConfig` with `name`, `base_url`, `api_key`,
`thinking`, and `reasoning_effort`. The default is `deepseek-v4-pro`, thinking
defaults to enabled for DeepSeek V4 models, and the provider sends DeepSeek's
OpenAI-compatible thinking fields through the shared model-settings builder.

The missing piece is user control. Users currently need to know the TOML schema
and edit config manually to change model or thinking behavior. That is
unfriendly for a terminal coding agent where users often discover the cost,
speed, or reasoning trade-off during an active session.

DeepSeek's documented OpenAI-compatible model set currently includes
`deepseek-v4-flash` and `deepseek-v4-pro`. Both support thinking enabled or
disabled, and thinking strength accepts `high` and `max`; DeepSeek also notes
that older `deepseek-chat` and `deepseek-reasoner` names are compatibility
aliases that will be deprecated later.

## Goals / Non-Goals

**Goals:**

- Let users choose between supported DeepSeek models without editing TOML.
- Let users choose thinking strength as one simple option: `none`, `high`, or
  `max`.
- Make `/model` interactive and keyboard-selectable by default, minimizing
  typing.
- Persist model and reasoning changes in `~/.deepy/config.toml` through the
  existing `[model] name`, `thinking`, and `reasoning_effort` fields while
  preserving existing API key, base URL, UI theme, context, logging, notify,
  and tool settings.
- Apply changed model settings to subsequent turns in the same interactive
  process.
- Keep direct command forms for users who already know the desired value.

**Non-Goals:**

- Adding non-DeepSeek providers or a general provider abstraction.
- Supporting arbitrary model IDs in the selection UI.
- Implementing custom per-model pricing display or budget enforcement.
- Changing session storage format, historical model metadata, or requiring
  users to migrate existing config files.
- Reworking DeepSeek reasoning replay behavior beyond using the active model
  and thinking settings.

## Decisions

1. Represent user-facing thinking choice as a normalized reasoning mode while
   persisting existing config fields.

   The UI should expose one concept:

   - `none`: thinking disabled.
   - `high`: thinking enabled with `reasoning_effort = "high"`.
   - `max`: thinking enabled with `reasoning_effort = "max"`.

   Internally, Deepy should normalize existing `thinking` and
   `reasoning_effort` fields into this `none|high|max` concept for validation,
   UI, provider mapping, and tests. It should write back through the existing
   TOML fields:

   - `none` -> `thinking = false`; preserve or omit `reasoning_effort`.
   - `high` -> `thinking = true`; `reasoning_effort = "high"`.
   - `max` -> `thinking = true`; `reasoning_effort = "max"`.

   This avoids forcing a new config-field migration on existing users. A future
   `reasoning_mode` field can be introduced later only if there is a stronger
   reason to simplify the file format.

   Alternative considered: persist a new `model.reasoning_mode` field. That
   would make the TOML match the UI, but it would also introduce another config
   shape immediately after users already have working `thinking` and
   `reasoning_effort` fields.

2. Keep a small built-in DeepSeek model catalog.

   The catalog should define stable metadata for selection and validation:

   - model id: `deepseek-v4-pro`, `deepseek-v4-flash`
   - label/description for picker display
   - whether thinking is supported
   - allowed reasoning modes: `none`, `high`, `max`
   - default reasoning mode, initially `max` to preserve Deepy's existing
     default behavior

   This avoids string duplication across config validation, `/model list`,
   welcome/status text, docs, and tests.

   Alternative considered: accept any model string everywhere. That is useful
   for advanced compatibility but undermines the selectable UX. A later escape
   hatch can preserve arbitrary IDs through direct config editing if needed,
   while `/model` remains catalog-based.

3. Make `/model` a two-step picker by default.

   Running `/model` with no argument should show the current model and reasoning
   mode, then open a model picker. After the user selects a model, Deepy should
   immediately open a reasoning-mode picker for `none`, `high`, and `max`.
   Empty or Esc cancellation should leave the saved config unchanged.

   Direct forms should remain available:

   - `/model list`
   - `/model set deepseek-v4-flash`
   - `/model reasoning none`
   - `/model reasoning high`
   - `/model reasoning max`

   The direct forms are useful in tests, scripts, and terminals where an
   interactive picker is unavailable.

4. Persist through a targeted config update helper that uses existing fields.

   `/model` should not serialize `settings_to_toml_dict`, because that path can
   contain masked secrets or computed values. It should use a dedicated helper
   that reads existing TOML, updates only `model.name`, `model.thinking`, and
   `model.reasoning_effort`, writes `0600` permissions, and preserves unrelated
   sections.

5. Refresh in-memory settings after saving.

   `run_interactive` currently passes a `Settings` object into each model turn.
   After `/model` persists changes, the interactive loop must reload settings
   and update prompt/welcome/status surfaces used for subsequent turns. Without
   this, the command would appear successful but the next model call would still
   use the old provider bundle.

6. Provider mapping remains centralized.

   `build_model_settings(settings)` should be the only place that maps
   `none|high|max` to DeepSeek request fields:

   - `none` -> `extra_body={"thinking": {"type": "disabled"}}`
   - `high` -> `extra_body={"thinking": {"type": "enabled"}}` plus
     `reasoning_effort="high"`
   - `max` -> `extra_body={"thinking": {"type": "enabled"}}` plus
     `reasoning_effort="max"`

   Existing compatibility with DeepSeek's `thinking` and `reasoning_effort`
   fields is not a transitional detail; it is the primary persistence contract
   for this change.

## Risks / Trade-offs

- [Risk] DeepSeek's model list or prices may change. -> Mitigation: keep the
  catalog small, centralized, and easy to update; avoid hard-coding price values
  into behavior.
- [Risk] Existing configs with `thinking = false` or invalid
  `reasoning_effort` need deterministic behavior. -> Mitigation: normalize
  loaded settings into the `none|high|max` user-facing model without requiring
  config migration.
- [Risk] Applying settings mid-session can surprise users if old and new model
  outputs are in one conversation. -> Mitigation: print a concise confirmation
  showing the active model and reasoning mode after saving.
- [Risk] A picker-only command can be hard to test or use in non-interactive
  terminals. -> Mitigation: keep direct argument forms and test the underlying
  handler with injected input functions.

## Migration Plan

1. Add model catalog and reasoning-mode validation.
2. Normalize existing `[model] thinking` and `reasoning_effort` fields into the
   user-facing reasoning mode on load.
3. Add targeted config update helpers that write `model.name`,
   `model.thinking`, and `model.reasoning_effort`.
4. Update provider settings to map the normalized reasoning mode into DeepSeek
   request fields.
5. Add `/model` command handling, picker UI, command completion, help text, and
   status refresh.
6. Update README/config docs and focused tests.

Rollback is straightforward because the change does not require a new persistent
model config field. Older code can continue reading `name`, `thinking`, and
`reasoning_effort`.

## Open Questions

- Whether `/model set <id>` should preserve the previous reasoning mode or ask
  for reasoning mode every time when used interactively with an argument.
