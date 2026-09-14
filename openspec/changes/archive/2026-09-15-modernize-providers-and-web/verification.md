# Implementation verification

Verified 2026-09-14/15 in the local development environment. Live scripts read credentials from process environments; no user configuration was changed. CLI Proxy authentication was supplied only to the probe process. No credentials or raw encrypted content are recorded here.

## Implemented call inventory

| Entry | Construction / transport | Evidence |
|---|---|---|
| Main agent | `llm/provider.py` → `DeepyResponsesModel` → `/responses`, `store=false` | `tests/llm/test_provider.py`; nine-model live function continuation |
| Subagents | inherit constructed model, or validate and construct within active provider | `tests/llm/test_agent.py::test_subagent_override_stays_in_active_provider`; existing subagent/MCP/audit tests |
| Input suggestions | `input_suggestions.py` → `client.responses.create`, fixed provider-local model | `tests/input_suggestions`, `tests/llm/test_thinking.py`, `tests/sessions/test_search_usage.py` |
| Compact / fold | shared provider bundle and current model settings | `tests/llm/test_compaction.py`, `tests/llm/test_context.py`, `tests/llm/test_cache_context.py`, runner compaction tests |
| Doctor | shared provider/config metadata, Responses label | `tests/cli/test_cli.py`, `tests/status` |
| Built-in search | `tools/runtime/web.py` → independent DeepSeek Messages request | `tests/tools/test_deepseek_search.py`; live application FunctionTool probe |
| WebFetch | existing local HTTP readable extraction | retained WebFetch tests in `tests/tools/test_tools.py` |
| Read images | retain JSON in local tool history; expand to validated Responses function-output image parts at request boundary | `tests/llm/test_read_responses.py` (all four providers, ordered batch images) |

Static search of production code, scripts and current user documentation found no OpenRouter, old search backend, `chat.completions`, or Chat Completions wrapper entry. Removed obsolete Chat replay, query preprocessing and SearXNG result parsing; kept protocol-neutral replay and HTTP decompression needed by WebFetch.

## Live capability evidence

| Provider/model | SDK function → output → second response | Streamed input image |
|---|---|---|
| DeepSeek `deepseek-flash` | passed; also `max` reasoning with reasoning items in both rounds | passed |
| MiMo `mimo-v2.5` | passed; also enabled/high reasoning with reasoning items in both rounds | passed |
| MiMo `mimo-v2.5-pro` | passed; enabled/high streamed function continuation passed | locally rejected; no image capability enabled |
| Kimi `kimi-k3` | passed; also `max` reasoning with reasoning items in both rounds | passed |
| CLI `gpt-6-astra` | passed | passed |
| CLI `gpt-5.6-sol` | passed | passed |
| CLI `gpt-5.6-terra` | passed | passed |
| CLI `gpt-5.6-luna` | passed on targeted retry after one upstream 500/EOF; high reasoning streamed continuation also passed | passed |
| CLI `gpt-5.5` | passed | passed |

Function probes require an executed tool result and the returned `verified-probe-ok` marker, not merely HTTP 200. Image probes use a generated four-quadrant PNG and verify red/green/blue/yellow in the correct order. All eight image probes produced streamed events and the expected answer. MiMo Pro rejection is covered at both provider serialization and Read tool boundaries.

Separate request acceptance probes tested all 35 catalog effort combinations: DeepSeek none/high/max; each MiMo model none/high; Kimi low/high/max; each CLI model none/low/medium/high/xhigh. All returned HTTP 200. This establishes parameter acceptance only; the SDK function and image tests above establish usable behavior. CLI non-none uses summary=auto; Kimi uses tool_choice=auto. No further upstream capabilities are inferred.

The application FunctionTool probe used an active MiMo conversation and actual `WebSearch`, completing two model rounds. Structured DeepSeek `server_tool_use` and correlated search-result blocks yielded ten displayed sources. Usage: input 8304, cache-read 384, output 590, server web-search requests 1. A separate service probe likewise succeeded while MiMo was active. These are individual observations, not token-cost guarantees. Native DeepSeek `web_fetch_20250910` was retested and rejected with HTTP 400; local WebFetch remains enabled.

Reproduce with explicitly opted-in calls (billable):

```sh
uv run python scripts/provider_smoke.py --live
uv run python scripts/provider_smoke.py --live --provider deepseek --reasoning max
uv run python scripts/provider_smoke.py --live --provider mimo --model mimo-v2.5-pro --reasoning high --stream
uv run python scripts/provider_image_smoke.py --live
uv run python scripts/provider_search_smoke.py --live --provider mimo
```

Provider environment variables are documented in both READMEs. An unset provider key skips its probe. Do not put real tokens into these files.

## Requirement-to-evidence map

Every added or modified requirement is listed below. Removed requirements are verified by static removal and final canonical spec inspection.

| Capability / requirement | Tests or explicit evidence |
|---|---|
| configuration: Config Initialization | CLI setup/init/reset/cancellation tests; profiles merge/permission tests |
| configuration: Missing API Key Guidance | CLI doctor tests; search-only missing-key test |
| configuration: Targeted Model Config Updates | `test_switching_and_editing_preserves_every_profile`, atomic failure test; classic/modern model tests |
| configuration: Provider-Scoped Credential Resolution | profile environment isolation/precedence/no-persistence tests |
| configuration: Supported Provider Model Catalog | catalog parameterization and nine-model live matrix |
| configuration: Versioned Provider Profile Selection | invalid/legacy profile tests, explicit setup tests |
| configuration: Provider Profile Reasoning | `tests/llm/test_thinking.py`; 35 effort acceptance probes |
| configuration: Responses Model Capability Metadata | catalog tests, image validation and four-provider Read continuation tests |
| deepseek-provider: DeepSeek Thinking | parameterized model-settings tests; live max continuation |
| deepseek-provider: Reasoning Mode Provider Mapping | model-settings tests; live effort acceptance matrix |
| deepseek-provider: Selected Model Provider Construction | provider request/identity tests and live function matrix |
| deepseek-provider: Input Suggestion Provider Settings | fixed model/reasoning mapping and suggestion request tests |
| deepseek-provider: Provider-Specific Balance Boundaries | retained status/session-cost tests |
| deepseek-provider: Responses Tool History And Streaming | SDK two-round tests, incomplete/failed stream fixtures, runner usage/cancellation/history tests, live streams |
| deepseek-provider: Unified Responses Provider Access | call inventory above and static transport scan |
| deepseek-provider: MiMo Responses Tool Compatibility | agent schema tests, SDK continuation, live MiMo reasoning continuation |
| deepseek-provider: Responses Image Content Normalization | `tests/llm/test_response_images.py`, `test_read_responses.py`, live image probes |
| input-suggestions: Input Suggestion Model | mapping and input-suggestion request/filter/cancellation tests |
| input-suggestions: Input Suggestion Usage Accounting | suggestion session tests; mixed-provider usage regression test |
| tools: MCP Web Search Preference | agent/MCP prompt tests, parameterized FunctionTool integration, existing MCP/subagent tests |
| tools: Bounded DeepSeek Search Execution | timeout/cancellation/key isolation/parser tests; implementation fixed limits and no HTTP retries |
| tools: DeepSeek Built-In Web Research | real/empty/error/partial/missing-result parser tests; live FunctionTool probe |
| tools: Responses Read Image Follow-Up | real SDK Read two-round request tests for all four providers; text-only and size rejection |
| image-understanding-input: Prompt Image Attachments | prompt/controller, classic terminal and modern prompt tests |
| image-understanding-input: Image Attachment Validation | MIME/base64/remote URL/8-image/32-MiB tests; draft retained on model change |
| image-understanding-input: Image Content Transport | normalization, runner/session tests, live image matrix |
| image-understanding-input: Responses Image Model Set | catalog parameterization, eight live image results, MiMo Pro rejection |
| session-context: Image Attachment Session Persistence | session persistence/redaction, provider replay and runner rollback tests |
| session-context: Independent Web Search Usage | `tests/sessions/test_search_usage.py`; runtime integration callback exactly once |
| subagents: Subagent Responses Model Resolution | inherited/valid/foreign/unknown override test plus retained subagent tool/MCP/audit tests |
| terminal-ui: Interactive Model Selection Command | classic provider/model picker and profile command tests |
| terminal-ui: Direct Model Command Forms | classic and modern direct-command tests |
| terminal-ui: Persistent Interactive Status Footer | retained status/terminal/modern UI tests with new provider fixtures |
| experimental-textual-tui: Textual Provider Model Selection | modern model/reset/cancel/save-failure tests |
| user-documentation: Provider Search And Image Documentation | synchronized English/Chinese README review and static obsolete-path scan |

## UI reproduction checks

Use a temporary config path to avoid modifying personal settings. Run Classic and Modern in turn. Configure DeepSeek, then MiMo; use `/model provider deepseek` and verify the saved key/model/reasoning/URL restore. Edit a provider with an empty password and verify its saved key remains. Cancel model selection and verify no config changes. Paste two supported images, remove one, submit an image-only prompt, and verify the transcript shows attachment labels. Paste an image then switch to MiMo Pro: submission must preserve the draft and show guidance. Switch back to an image model and submit. With MiMo configured but no DeepSeek key, built-in search must report the missing search key while conversation, MCP search and local WebFetch remain available. Automated UI tests cover these component and command paths; no claim of a manual native clipboard session is made.

## Review notes

New focused modules hold profiles, Responses image normalization, native search and auxiliary usage accumulation. Existing large runner/session/UI modules use narrow integration changes. Read JSON remains the local history/UI format; image conversion occurs only at the outgoing request boundary to preserve redaction and avoid breaking tool rendering. Search accounting is separate from context checkpoints. Real account configuration and release metadata are untouched.

Focused verification: 77 tests passed for config/provider/thinking/replay/images/suggestions/search, 34 passed for Read/image/prompt/terminal integration, 37 passed for provider failure/usage/suggestions, 17 passed for subagent/search/session integration, 19 passed for picker/meta/config follow-up, 11 passed for search bounds, and the final Modern image-switch regression passed. A focused broad run exposed stale picker labels and a JSON utility import convention; both were corrected and their targeted tests passed.

Final full gate: `uv run pytest -q` — **1022 passed in 59.67s**. `uv run ruff check src tests scripts`, `uv run ty check src`, `git diff --check`, and `openspec validate modernize-providers-and-web --type change --strict` all passed. MiMo Pro opt-in image probe returned `rejected_as_expected` locally before any image request.

Official request references checked for adapter behavior: [DeepSeek Responses](https://api-docs.deepseek.com/guides/responses_api/), [MiMo Responses](https://mimo.mi.com/docs/en-US/api/chat/responses), [Kimi Responses](https://platform.kimi.com/docs/api/responses). CLI Proxy capability claims are limited to the configured local endpoint and successful model probes in this record.

Archive completed 2026-09-15. All 33 tasks are complete. Canonical synchronization applied 16 added, 19 modified and 16 removed requirements across ten capabilities. Final `openspec validate --specs --strict`: **25 passed, 0 failed**. The installed validator also required replacing twelve historical Purpose placeholders; these edits summarize existing requirements and introduce no new behavior. The archive command initially reported one incomplete task because task 7.6 was the archive operation itself; it is now complete.
