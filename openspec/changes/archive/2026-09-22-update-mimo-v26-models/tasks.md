## 1. Catalog, configuration and budgets

- [x] 1.1 Replace the MiMo catalog with V2.6 Flash/Pro, make Flash the default and mark both image capable; verify focused configuration tests cover exact catalog membership, defaults, retained thinking modes and rejection of old IDs without settings mutation.
- [x] 1.2 Add specific replacement guidance for removed models in active/inactive profiles and model-limit override keys; verify tests identify the offending setting, suggest the corresponding V2.6 model, preserve file bytes, redact credentials and accept explicitly corrected profiles with valid preserved overrides.
- [x] 1.3 Register V2.6 limits with nominal 1M, conservative 1,000,000 runtime context, documented 131,072 output and current evidence date/source; verify context tests cover the unchanged 32,768 default, output boundary acceptance/rejection and smaller user context caps.

## 2. Responses, images and auxiliary models

- [x] 2.1 Update direct-MiMo tool-schema compatibility for both V2.6 models; verify agent/schema tests preserve optional runtime defaults and provider isolation, and mocked Responses round-trip tests execute a function call and return its result with the matching call ID for each new model.
- [x] 2.2 Move fixed MiMo input suggestions to V2.6 Flash with thinking disabled; verify suggestion tests cover both active MiMo models, provider credentials, storage disabled and separate usage accounting.
- [x] 2.3 Replace old Pro text-only assumptions with positive V2.6 Flash/Pro image cases and synthetic unsupported-capability fixtures; verify focused tests cover prompt/Read images, history replay, inherited and explicit subagent models, image limits and cross-model reasoning isolation without rewriting historical identity.
- [x] 2.4 Verify both new IDs through the shared Responses construction path with deterministic tests for main/subagent/compaction/suggestion/doctor requests, including none/high reasoning and streamed text/reasoning/completion handling; keep live API evidence supplemental and CI independent of credentials.

## 3. UI and documentation

- [x] 3.1 Update classic and modern model choices, completions and help examples; verify focused UI tests show only the two V2.6 choices with image support, accept both direct model commands, preserve settings on removed-ID rejection and allow Pro image attachment submission.
- [x] 3.2 Update README.md, README.zh-CN.md, both model-context guides and index.html after implementation tests pass; review matching model IDs, limits, suggestion routing, text/image application scope, retirement date and explicit TOML migration instructions including model-limit keys.
- [x] 3.3 Audit remaining V2.5 references with `rg`; verify each retained reference is rejection/migration coverage, historical identity or archived OpenSpec evidence, rather than current supported behavior, and leave archive/history files intact.

## 4. Integrated validation

- [x] 4.1 Run affected configuration, LLM, image, subagent, suggestion and both UI focused tests through `uv run pytest`; verify every added/modified scenario has deterministic coverage and resolve failures before the full gate.
- [x] 4.2 Run `uv run ruff check src tests`, `uv run ty check src`, `uv run pytest -q` and `openspec validate update-mimo-v26-models --type change --strict`; record passing results before marking implementation complete. Archive only after implementation/verification, then validate canonical specs as required by the repository workflow.


## Validation record (2026-09-22)

- Configuration/LLM/suggestion focused suite: 234 passed.
- Classic/modern UI focused suite: 321 passed.
- Additional shared MiMo routing/agent tests: 11 passed; direct UI selection/retirement tests: 3 passed.
- Full suite: `uv run --no-sync pytest -q` — 1135 passed in 63.24s.
- The final expanded subagent capability matrix was verified separately: 8 passed (includes four additional synthetic text-only cases added after full-suite collection).
- `uv run --no-sync ruff check src tests`, `uv run --no-sync ty check src`, scoped strict OpenSpec validation and `git diff --check` passed.
- `UV_CACHE_DIR` pointed to a temporary writable directory. Session-writing suites ran with sandbox escalation because restricted runs could not create their temporary project databases under `~/.deepy`; those permission failures were resolved by the permitted reruns.
- Current source/docs retain old IDs only for migration/rejection or historical identity tests. Canonical specs remain unchanged until archival; the six delta specs carry the updated contracts.
- No release, tag, push or archive performed.
