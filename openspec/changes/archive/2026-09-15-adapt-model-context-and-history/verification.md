# Verification — 2026-09-15

## Evidence and implementation decisions

- Limit evidence, units and reference links: `docs/model-context.md` and
  `docs/model-context.zh-CN.md`. Nominal 1M windows use 1,000,000. Nominal K output
  limits use decimal conservative ceilings. Kimi's explicit output parameter
  ceiling is recorded separately. No shared-window exception is assumed without
  evidence. CLI Proxy remains `proxy-unverified`.
- `model_limits`, `request_budget`, `history_projection`, `history_migration`,
  `history_state` and `work_boundary` isolate new behavior from large existing modules.
- Outgoing SDK payloads are checked after tool conversion and image normalization;
  continuations stop recoverably if oversized. This preserves completed tool work
  instead of retrying side effects. Subagents receive their own resolved limits.
- Every replay is revalidated. There is no persistent cache that can silently
  restore an older oversized view. Existing archives retain originals; a content
  revision guard prevents a summary from overwriting concurrent history updates.
- A live switch from MiMo/Kimi to CLI Proxy exposed provider-local message IDs.
  Replay now strips foreign/unproven item IDs, retaining portable `call_id` pairs.
- Kimi only accepts `auto` tool choice. Its summary agent registers no tools/MCP;
  other summary requests disable tools. Summary clients disable SDK retries.
- Successful summary usage is recorded immediately, including per-model usage,
  independently of the conversation occupancy checkpoint.

## Requirement-to-test mapping

Paths below are relative to the repository root. Existing canonical suites remain
part of the full gate; the listed tests focus on the new behavior.

| Capability / requirement | Tests or evidence |
| --- | --- |
| configuration / Context Compaction Configuration | `tests/config/test_model_limits.py`, `tests/config/test_settings.py`, `tests/llm/test_history_budget.py::test_summary_uses_its_own_actual_reserve` |
| configuration / Model Limit Overrides | `tests/config/test_model_limits.py` (nine-model catalog, min caps, independent profiles, invalid values, redaction, read-only display, atomic save failure) |
| model-context-budget / Model Limit Evidence | Bilingual model-context tables; `test_catalog_limits_are_explicit_and_conservative` |
| model-context-budget / Complete Request Budget | `tests/llm/test_history_budget.py` (prefix/tools, new input, images, checkpoint); `tests/llm/test_provider.py::test_tool_continuation_budget_rejects_before_second_http_and_preserves_work` |
| model-context-budget / Purpose-Specific Output Budgets | `tests/llm/test_provider.py`, `tests/llm/test_compaction.py`, `tests/llm/test_subagent_read_capabilities.py`, existing input-suggestion and auxiliary-usage tests |
| model-history-switch / Non-Destructive Target History | `test_reasoning_does_not_cross_model_or_endpoint_or_missing_origin`, `test_foreign_server_ids_are_removed_without_breaking_call_ids`, `test_parallel_tool_group_is_indivisible_and_incomplete_is_error`, `test_summary_preserves_tool_arguments_and_pairing` |
| model-history-switch / Safe Selection Boundary | `tests/ui/test_model_history_status.py` (Classic lease, Modern busy/tool guards); `history_groups` incomplete diagnostics |
| model-history-switch / Bounded History Migration | `tests/llm/test_history_budget.py` (budgeted chunks/merge, indivisible groups, call limit, timeout, cancellation, final target check, stale revision); `tests/ui/test_model_history_status.py::test_summary_cancellation_interrupts_running_call` |
| model-history-switch / Explicit Image History Reduction | `test_image_reduction_requires_opt_in_and_uses_only_last_source`; Modern exact option/attachment test; unchanged ordinary focus tests |
| session-context / Usage Accounting | Existing session/usage suites; successful summary accounting and checkpoint tests in `test_history_budget.py` |
| session-context / Context And Compact Display | `test_reported_checkpoint_switch_and_resume_display`, existing Classic/Modern/status suites updated for unproven checkpoints |
| session-context / Image Attachment Session Persistence | Existing image/Read/session suites, `test_image_reduction_requires_opt_in_and_uses_only_last_source`, Modern failure/attachment test |
| session-context / Context Checkpoint Identity | `test_checkpoint_adds_uncovered_input_and_cross_model_downgrades`, `test_unknown_checkpoint_is_not_precision`, `test_old_schema_migration_is_idempotent_and_keeps_messages`, UI checkpoint test |
| terminal-ui / Bottom Context Status Accuracy | `tests/ui/classic/test_terminal.py`, shared `test_reported_checkpoint_switch_and_resume_display` |
| terminal-ui / Context Window Display Semantics | `tests/status/test_status.py`, shared context-label tests and Classic footer tests |
| terminal-ui / Model Switch Context Recovery | Classic guard and image controller tests, runner preparation and draft restoration path |
| experimental-textual-tui / Textual Provider Model Selection | `tests/ui/modern/test_app.py`, `tests/ui/test_model_history_status.py` (busy/tool rejection, draft/images restored, exact compact option, reported target usage) |
| user-documentation / Model Context And History Documentation | Both READMEs and both model-context documents; formulas, sources, proxy caps, original history, explicit lossy image summaries and usage attribution checked together |

## Small live smoke

Script: `scripts/smoke_model_history.py`, enabled only with `DEEPY_LIVE_CONTEXT=1`.
Standard key environment variables were used; CLI Proxy token was supplied only
to the process environment. User config was not changed. Text/tool history used
a temporary durable session shared through successive model targets. Image
checks used a separate tiny 32x32 valid PNG request.

| Model | Text and prior tool-result replay | Image response |
| --- | --- | --- |
| deepseek-flash | Passed | Passed |
| mimo-v2.5 | Passed | Passed |
| mimo-v2.5-pro | Passed | Not applicable: text-only |
| kimi-k3 | Passed | Passed |
| gpt-6-astra | Passed | Passed |
| gpt-5.6-sol | Passed | Passed |
| gpt-5.6-terra | Passed | Passed |
| gpt-5.6-luna | Passed | Passed |
| gpt-5.5 | Passed | Passed |

Scope details: the initial image fixture was invalid and replaced. Kimi's smoke
reasoning was corrected from unsupported `none` to supported `low`. MiMo Pro
sometimes re-called the offered echo tool and hit the deliberately short smoke
turn limit; the prior tool-history response passed when new tool calls were
disabled. The corrected script makes that policy explicit. The foreign-ID
failure was a runtime bug, fixed and covered by regression and repeated live
switches. No maximum-context, maximum-output, web-search or proxy-limit claims
are inferred from these small requests. Image success means a completed response
to a valid image input, not a vision accuracy benchmark.

## Gates

- Earlier full implementation gate: 1,073 passed in 60.94 seconds.
- Added UI command/failure/cancellation suite: 7 passed.
- Final full gate: `uv run pytest -q` — **1,078 passed in 60.36 seconds**.
- `uv run ruff check src tests` — passed.
- `uv run ty check src` — passed.
- `openspec validate adapt-model-context-and-history --type change --strict` — passed.
- `git diff --check` — passed.
- A subsequent attachment-chip refresh received the focused UI recovery suite again;
  no model/request/storage changes followed the full gate.
- No archive, commit, push, release or user config update is part of this apply.

## Follow-up regression: schema `type` is not always a string

The reported streaming `hi` crash was reproduced with the full built-in tool
schemas. The recursive budget estimator used set membership on `schema.type`;
JSON Schema permits array-valued union types, and a properties object can also
contain a property named `type` whose value is a nested schema. Both are unhashable.
The estimator now verifies that the image discriminator is a string before
checking image types; all other schema content remains in the recursive estimate.

`tests/llm/test_request_budget_schema.py` covers unions, nested `type` properties,
input immutability, and actual SDK streaming with the complete Deepy tool set for
all nine models. Before the fix, 10 of these 12 tests failed with the reported
exception; after the fix, all 12 pass. The broader focused suite passed 48 tests.
The installed `deepy-cli` interpreter (openai-agents 0.18.2) was also checked:
it loads this checkout, and all nine models build a streaming request containing
all 13 built-in tools. These installed-runtime checks made no network requests.

Follow-up gates: **1,090 tests passed in 61.64 seconds**; Ruff, ty, strict OpenSpec validation and `git diff --check` passed.

## Follow-up: compact context footer

Both interfaces now render compact K/M token counts and short state symbols,
for example `ctx 12.5K/1M~ (1.3%)`. Full numeric values, remaining capacity and
source/readiness descriptions remain in status/doctor diagnostics. Regression
coverage checks unit boundaries, reported and estimated usage, model switching,
unknown usage, compaction hints and both UI integrations. English and Chinese
context documentation describe the symbols.

Focused history/status tests: **15 passed**. Full suite: **1,098 passed in
62.04 seconds**. Ruff, ty, strict OpenSpec validation and `git diff --check` passed.
