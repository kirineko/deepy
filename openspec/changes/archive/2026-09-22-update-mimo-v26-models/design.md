## Context

See proposal.md for motivation and scope. Model IDs currently appear in the shared provider catalog, model-limit table, fixed suggestion routing, MiMo schema-compatibility predicate, UI help and tests. All saved provider profiles and model-limit overrides are validated when settings load, including inactive profiles. Removing an ID without recovery guidance therefore affects users who are not currently using MiMo.

The existing shared capability catalog controls prompt attachments, Read images, history projection and subagents. Existing tests use V2.5 Pro as a text-only negative fixture; a mechanical rename would incorrectly preserve that restriction for V2.6 Pro.

### Evidence from exploration (2026-09-22)

- [Official model list](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model) lists V2.6 Flash/Pro with multimodal understanding, nominal 1M context and 128K output, and schedules V2.5/V2.5 Pro retirement for 2026-10-21 10:00 Asia/Shanghai. UltraSpeed is a custom service, outside this catalog update.
- [Official Responses reference](https://mimo.mi.com/docs/zh-CN/api/chat/responses) explicitly permits `max_output_tokens` through 131072. `reasoning.effort=none` disables thinking; other supported efforts enable it without distinct intensity guarantees.
- Using `MIMO_API_KEY` against the official endpoint, `/models` returned both IDs. Each model completed four Responses probes with HTTP 200: text (`OK`), a synthetic image with red left/blue right halves (both correctly identified), function-call generation (`probe_echo` with `value=hello`), and `high` reasoning with SSE (`17 * 19 = 323`, reasoning/text deltas and completion).
- These probes did not exercise Deepy's complete agent loop, tool-result replay, audio/video input or maximum context/output sizes. Tool calls were generated but no side-effecting tool was executed. No secret is stored in these artifacts.

## Goals / Non-Goals

**Goals:** Keep one shared catalog decision for image support; preserve existing Responses transport, provider-local credentials, thinking controls and transactional selection; make removal recoverable with precise configuration guidance.

**Non-Goals:** New modality pipelines, API fallback, changing generic history semantics, generalized model discovery, automatic alias migration, or unrelated restructuring of large modules. Public documentation updates occur with tested implementation, not during this proposal.

## Decisions

1. **Replace the supported catalog, without aliases.** Use `mimo-v2.6-flash` as the default and suggestion model, and `mimo-v2.6-pro` as the alternate. Both support images. Keeping old IDs until the provider deadline would leave newly saved configurations dependent on models scheduled for retirement; silently resolving aliases would obscure the selected model and user cost/performance choice.

2. **Reject old configuration with actionable guidance.** When an active or inactive profile selects a removed ID, identify `providers.mimo.model` and suggest `mimo-v2.5` → `mimo-v2.6-flash` or `mimo-v2.5-pro` → `mimo-v2.6-pro`. If a removed ID appears in `providers.mimo.model_limits`, identify the offending entry and instruct the user to rename it to the replacement or remove the override. A direct edit of the existing TOML is a recovery path even when startup cannot load settings. Preserve key, URL, reasoning, unrelated settings and file bytes until the user explicitly edits or completes setup. Do not print credential values. Centralize the short replacement guidance in a focused config helper if multiple validation boundaries need it; avoid duplicating large handlers.

3. **Reuse existing capability and tool boundaries.** Set both catalog entries image capable; update the direct-MiMo schema predicate for both new IDs and retain its provider guard. Use existing image normalization and Responses function-call/result transport. Removing the compatibility transform is a separate change requiring stronger schema evidence than the simple live function probe. Negative image tests use an explicit synthetic unsupported capability fixture, not a supported V2.6 model.

4. **Separate nominal context from exact output limits.** Retain 1,000,000 as the conservative runtime interpretation of 1M, with no exact-context assertion. Set the maximum output to 131,072 based on the API reference and update evidence date/source. Retain the 32,768-token default request budget, user caps and shared-window safety policy. Continuing to use 128,000 would unnecessarily reject values explicitly allowed by the API; increasing the default request budget is unnecessary for this upgrade.

5. **Preserve historical identity.** Update current selectable models and help, not archived OpenSpec changes or historical session metadata. Old session model names may remain descriptive evidence; replay to a new model uses the existing cross-model history projection and reasoning provenance rules. Do not global-replace historical identifiers or rewrite saved transcripts.

## Risks / Trade-offs

- Existing active/inactive profiles can block startup → Cover both with deterministic configuration tests and document exact TOML replacements, including model-keyed overrides.
- All supported catalog models become image capable → Preserve unsupported-capability branch coverage through synthetic fixtures while adding positive Pro image tests across UI, Read, replay and subagent paths.
- Simple API probes are weaker than end-to-end agent validation → Add mocked Responses tool continuation and image normalization regression coverage for both new IDs; live smoke tests remain supplemental, never credential-dependent CI tests.
- The provider supports more modalities than Deepy → Describe the models as multimodal while explicitly limiting Deepy's support to text/image input; no claim of verified audio/video or extreme capacity.

## Migration Plan

Implement the delta requirements and focused tests, update both documentation languages and website copy, then run Ruff, ty, the full test suite and scoped OpenSpec validation. Archive only after implementation and validation finish; verify canonical specs after archival. Release/tag/push is outside this change.

Document explicit replacement of `[providers.mimo].model` and any corresponding `[providers.mimo.model_limits."<model-id>"]` table key. Preserve valid override values and credentials; reject invalid limits normally. Existing transcript history stays readable and uses normal model switching when resumed under the new configuration.

Rollback before publication is a code revert without configuration writes. Users who explicitly selected V2.6 would need to choose a model supported by the reverted build; the provider's announced retirement makes an old-model rollback unsuitable after the deadline.
