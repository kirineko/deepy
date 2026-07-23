## Context

Deepy constructs model access through a static `PROVIDER_CATALOG` and a single
`build_provider_bundle` path that currently always wraps
`OpenAIChatCompletionsModel`. Thinking settings are provider-specific
`extra_body` shapes (DeepSeek `thinking`/`reasoning_effort`, OpenRouter
`reasoning`, Xiaomi `thinking.type`). Image support is gated by
`model_supports_image_input`.

CLIProxyAPI exposes GPT-5.6 models locally at `http://127.0.0.1:8317/v1` with
working Responses API (`/v1/responses`), Chat Completions (`/v1/chat/completions`),
streaming, tools, image input, and `reasoning.effort` values including
`none`/`low`/`medium`/`high`/`xhigh`. GPT-5.6 guidance prefers Responses for
reasoning and tool-calling workflows.

## Goals / Non-Goals

**Goals:**

- Add `localhost` as a first-class provider with curated GPT-5.6 models.
- Use Responses API for the main conversation path on localhost.
- Support thinking modes `none`/`low`/`medium`/`high`/`xhigh` (default
  `medium`) via Responses `reasoning.effort`.
- Support image input for all three curated localhost models.
- Keep API key storage identical to other providers (`config.toml` /
  `DEEPY_API_KEY`).
- Use a cheap localhost suggestion path: Chat Completions + `gpt-5.6-luna` +
  `reasoning_effort=none`.
- Infer `localhost` from `127.0.0.1` / `localhost` hosts when `provider` is
  missing.

**Non-Goals:**

- Adding GPT-5.6 Pro mode, `max` effort, programmatic tool calling, or
  multi-agent Responses features.
- Making Responses the default for DeepSeek/OpenRouter/Xiaomi.
- Replacing Chat Completions sanitization/replay logic for existing providers.
- Shipping a GUI for CLIProxyAPI itself or managing OAuth tokens for it.
- Changing Deepy's default provider away from DeepSeek.

## Decisions

1. Provider id is `localhost`, default base URL is `http://127.0.0.1:8317/v1`.

   OpenAI Python clients expect the `/v1` suffix. Users can override `base_url`
   in TOML if their proxy listens elsewhere.

   Alternative considered: store `http://127.0.0.1:8317` and append `/v1` in
   code. Rejected because other providers already persist the full OpenAI-style
   base URL including `/v1`.

2. Add `ProviderInfo.api: Literal["chat_completions", "responses"]`.

   `build_provider_bundle` branches on this field:
   - `chat_completions` (default): existing `DeepyOpenAIChatCompletionsModel`
   - `responses`: `OpenAIResponsesModel` with the same `AsyncOpenAI` client

   Alternative considered: hard-code `if provider == "localhost"`. Rejected
   because an explicit API field documents the transport contract and leaves
   room for future Responses providers without more provider-id checks.

3. Localhost reasoning uses `ModelSettings(reasoning=Reasoning(effort=...))`.

   Do not send DeepSeek/OpenRouter/Xiaomi chat `extra_body` thinking payloads
   for localhost main turns. `build_thinking_extra_body("localhost")` returns
   `{}` for the Responses path. Input suggestions still use Chat Completions
   and send `{"reasoning_effort": "none"}` for localhost.

4. Localhost thinking modes are `none`, `low`, `medium`, `high`, `xhigh`.

   Persist through existing `model.thinking` + `model.reasoning_effort`:
   - `none` → `thinking=false`, `reasoning_effort="none"`
   - other modes → `thinking=true`, `reasoning_effort="<mode>"`
   - defaults: model `gpt-5.6-terra`, thinking `medium`

   CLIProxyAPI may coerce Responses `none` to `low`; Deepy still treats
   user-facing `none` as disabled thinking.

5. Image support is catalog-driven and allowlisted in
   `model_supports_image_input`.

   All three localhost models set `supports_image_input=True`. Runtime gating
   stays in `multimodal.py` so unsupported models continue to strip images
   before request.

6. Input suggestions for localhost use fixed `gpt-5.6-luna` + none effort.

   This mirrors DeepSeek's fixed `deepseek-v4-flash` suggestion model rather
   than OpenRouter/Xiaomi's "reuse main model" approach, because GPT-5.6 terra
   / sol are unnecessarily expensive for 2–12 word suggestions.

7. Infer provider from host only for loopback hosts.

   `infer_provider_from_base_url` returns `localhost` when hostname is
   `127.0.0.1` or `localhost`. Other private IPs remain unknown and keep
   DeepSeek-style fallback unless `model.provider` is explicit.

## Risks / Trade-offs

- [Risk] Responses path bypasses Chat Completions sanitizers/reasoning replay
  helpers. → Mitigation: keep Responses construction minimal; verify streaming,
  tools, and session replay with live CLIProxyAPI; add focused construction
  tests; do not reuse chat-only sanitizers unless a defect appears.
- [Risk] Proxy remaps Responses `effort=none` to `low`. → Mitigation: document
  in proposal/specs; persist and display `none` as the user's disabled choice;
  suggestions use Chat Completions `reasoning_effort=none`, which was measured
  to keep `reasoning_tokens=0`.
- [Risk] Catalog/UI/config error strings hard-code provider lists.
  → Mitigation: update provider set and help text in config_io/cli/picker
  together; prefer catalog-driven picker values.
- [Trade-off] Main path uses Responses while suggestions use Chat Completions.
  Acceptable because suggestions are short, non-tooling background calls and
  Chat Completions is already proven on the local proxy.

## Migration Plan

1. Ship catalog + Responses branch behind the new provider id; DeepSeek remains
   default.
2. Existing configs without `localhost` are unchanged.
3. Users opt in via `deepy config setup`, `/model` provider picker, or by
   writing `provider = "localhost"` with a localhost `base_url`.
4. Rollback: remove provider catalog entry and Responses branch; configs with
   `provider = "localhost"` would fall back through existing unsupported-
   provider / default resolution behavior after revert.

## Open Questions

- None for this change. GPT-5.6 Pro mode / `max` effort can be a follow-up if
  users need them.
