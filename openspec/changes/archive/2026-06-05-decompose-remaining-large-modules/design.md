# Design: decompose remaining large modules

## Goals and non-goals

- **Goal**: bring `agents.py`, `settings.py`, `runner.py` under 800 lines via
  mechanical, behavior-preserving extraction along existing concern seams.
- **Goal**: remove systemic test-harness duplication in the two worst suites by
  introducing shared `conftest.py` fixtures, without changing any assertion.
- **Non-goal**: refactoring logic, renaming public symbols, changing config file
  format, tool wiring, or LLM turn semantics.
- **Non-goal**: splitting the large test files by concern (Lever B). Only
  de-duplication via fixtures (Lever A) is in scope.

## Guiding principles (reused from `split-oversized-modules`)

1. **Mechanical moves only.** Cut a cluster, paste into a sibling module, fix
   imports. No behavior edits in the same step.
2. **Preserve the import surface.** The original module re-exports every symbol any
   caller or test imports, with `# ruff: noqa: F401` where needed.
3. **Acyclic dependency direction.** Extracted helpers must not import back into the
   original module. Where a moved function needs a monkeypatchable name, resolve it
   at call time through the original module (the established patchable pattern).
4. **Gate after every module.** Run `ruff`, `ty`, and the module's focused tests
   before moving on.

---

## 1. `tools/agents.py` (1079 → target <800) — LOW risk

Only three importers: `src/deepy/llm/agent.py` (`build_function_tools`),
`tests/audit/test_audit.py` (`build_function_tools`), and
`tests/tools/test_tools.py` (`build_function_tools`, `make_mimo_compatible_tool_schema`).
The file is one large builder plus three free-function clusters.

```
agents.py
├─ build_function_tools (352)         ── STAYS (tool registry/wiring; risky to split)
├─ _test_shell_* policy helpers (19)  ── STAYS (small, builder-adjacent)
│
├─► tools/tool_args.py        (~90)   argument extraction & coercion
│     _tool_args, _string_arg, _optional_string_arg, _int_arg,
│     _optional_int_arg, _bool_arg, _invalid_tool_arguments_result,
│     _merge_tool_result_metadata
│
├─► tools/arg_repair.py       (~116)  best-effort JSON / argument repair
│     _repair_tool_arguments, _quote_unquoted_read_ranges,
│     _replace_unquoted_python_literals, _remove_trailing_commas,
│     _is_identifier_char
│
└─► tools/schema_compat.py    (~80)   schema validation + MiMo compatibility
      make_mimo_compatible_tool_schema, _remove_nullable_required_fields,
      _schema_type_allows_null, _validate_args_against_schema,
      _schema_value_matches, _schema_enum_matches
```

- **Dependency direction**: `agents.py → {tool_args, arg_repair, schema_compat}`.
  `schema_compat` may use `tool_args`; both are leaf-ish. No back-imports.
- **Surface to preserve**: re-export `build_function_tools` and
  `make_mimo_compatible_tool_schema` from `agents.py`.
- **Result**: agents.py ≈ 470 lines.
- **Risk**: minimal. `build_function_tools` references the moved arg/schema helpers;
  they become plain imports.

---

## 2. `config/settings.py` (1070 → target <800) — MEDIUM risk

Widely depended on: 38 files import `deepy.config` (through `config/__init__.py`),
**and** several modules import `deepy.config.settings` directly (notably
`src/deepy/llm/provider.py` and many tests). Therefore `settings.py` **must remain a
real module that re-exports the full surface** — it becomes a thin hub, not deleted.

```
config/settings.py  ── thin re-export hub (keeps deepy.config.settings.* working)
│
├─► config/providers.py   (~280)   provider catalog + queries + value coercion
│     ModelInfo, ProviderInfo, PROVIDER_CATALOG, provider_info_for,
│     resolve_provider, infer_provider_from_base_url, is_*_provider/model,
│     default_*_for_provider, thinking/reasoning mode helpers,
│     normalize_reasoning_effort, mask_secret, _as_* coercers
│
├─► config/schema.py      (~300)   config dataclasses + from_mapping parsers
│     ModelConfig, ContextConfig, LoggingConfig, NotifyConfig,
│     WebSearchToolConfig, TestShellToolConfig, ToolsConfig,
│     McpWebSearchConfig, McpConfig, UiConfig, Settings
│
└─► config/config_io.py   (~400)   load / write / update + UI selectors
      load_settings, settings_to_toml_dict, write_config,
      update_config_model_settings, update_config_theme,
      update_config_ui_interface, update_config_ui_choice,
      update_config_textual_theme, update_config_input_suggestions_enabled,
      update_config_view_mode, update_config_audit_mode,
      ui_*_number / ui_*_from_selection, is_valid_* predicates,
      _read_toml_mapping, _write_private_toml, _drop_empty
```

- **Dependency direction** (acyclic, leaf → trunk):
  `providers.py` (no intra-config deps) ← `schema.py` (uses providers for
  `provider_info`, reasoning resolution) ← `config_io.py` (builds/writes
  `Settings`, uses providers + schema). `settings.py` imports from all three and
  re-exports.
- **Surface to preserve**: `config/__init__.py` keeps its current
  `from .settings import (...)` block unchanged; `settings.py` re-exports the full
  set so both `deepy.config.X` and `deepy.config.settings.X` keep resolving.
- **Result**: settings.py ≈ 60–120 lines (imports + `__all__`).
- **Risks / watch-points**:
  - **Import cycle**: `schema.py` importing `providers.py` is fine; ensure
    `providers.py` does not import `schema.py`. `mask_secret` and `_as_*` belong with
    providers/coercion, not schema.
  - **`write_config` (87 lines)** references dataclasses + providers; keep it in
    `config_io.py` with explicit imports.
  - **`ty` typing**: dataclass `from_mapping` classmethods returning `Self` move
    cleanly; verify no forward-reference breakage after the move.

---

## 3. `llm/runner.py` (943 → target <800) — MEDIUM risk

The LLM turn orchestrator. `run_prompt_once` (363) stays; three helper families move.

```
llm/runner.py  ── run_prompt_once (363) + RunSummary + _run_status +
                  _resolve_loaded_skills + _max_turns_output + re-exports
│
├─► llm/runner_approvals.py   (~150)
│     _approval_decisions, _pending_approval_from_interruption,
│     _approval_preflight, _approval_tool_name, _approval_arguments,
│     _approval_call_id, _approval_server_name, _approval_action_kind
│
├─► llm/runner_errors.py      (~100)
│     format_deepseek_api_error, DeepSeekErrorStatus,
│     _api_status_error_message, _api_status_error_response,
│     _api_error_body_field, _safe_int
│
└─► llm/runner_interrupt.py   (~200)
      _cancel_stream_result, _watch_stream_interrupt, _finish_interrupt_task,
      _reconcile_interrupted_session_tail, _is_user_prompt_item,
      _item_text_content, _interrupted_tool_output_items,
      _missing_output_items_for_call, _function_call_id,
      _function_call_output_id, _interrupted_marker_item,
      _is_interrupt_marker_item, _pending_questions_from_tool_output
```

- **Surface to preserve**: re-export `run_prompt_once`, `RunSummary`,
  `DEFAULT_MAX_TURNS`, `format_deepseek_api_error` from `runner.py`.
- **CRITICAL monkeypatch watch-point**: tests patch
  `deepy.llm.runner.ensure_context_ready`, `.log_debug_event`,
  `.launch_notify_script`, and `.log_api_error`. These must remain module attributes
  of `runner.py` and be **called from `run_prompt_once` (which stays in `runner.py`)**.
  Before moving any helper, verify it does not itself call one of these patched
  names; if one does, keep that helper in `runner.py` or resolve the name at call
  time through the runner module. The error `location` strings
  (`"deepy.llm.runner.run_prompt_once"`) stay valid because `run_prompt_once` does
  not move.
- **Result**: runner.py ≈ 430 lines.
- **Risk**: the interrupt/session-tail helpers are interdependent; move them as one
  cohesive unit to avoid a cross-module web.

---

## 4. Test harness fixtures (Lever A only)

Root cause: **no `conftest.py`**, **0 fixtures**, harness setup duplicated per test.

### `tests/ui/modern/conftest.py`

```python
@pytest.fixture
def make_tui_app(tmp_path):
    def _make(run_once=_idle_run_once, settings=None, **kw):
        return DeepyTuiApp(settings=settings or Settings(),
                           project_root=tmp_path, run_once=run_once, **kw)
    return _make

@asynccontextmanager
async def tui_harness(app, size=(100, 32)):
    async with app.run_test(size=size) as pilot:
        prompt = app.query_one("#prompt-input", PromptTextArea)
        try:
            yield app, pilot, prompt
        finally:
            app.exit()
```

- Collapses the ~88 `run_test` open/close rituals, ~132 constructions, ~117
  `app.exit()` and ~102 `query_one("#prompt-input", ...)` lines into one call site.
- Module helpers already present (`_idle_run_once`, `_submit_prompt`,
  `_wait_for`, `_choose_inline_option`, ...) move into `conftest.py` so they are
  shared, not file-local.

### `tests/tools/conftest.py`

```python
@pytest.fixture
def make_runtime(tmp_path):
    def _make(**kw):
        return ToolRuntime(cwd=tmp_path, settings=Settings(), **kw)
    return _make
```

- Collapses the 117 inline `ToolRuntime(...)` constructions.
- The 8 existing module helpers (`read_v3`, `write_v3`, `update_v3`,
  `preflight_v3`, `decode`, ...) move into `conftest.py`.

### Migration discipline

- Migrate **setup/teardown only**. Every `assert`/`await ...` expectation stays
  byte-identical.
- Migrate incrementally; run `pytest` on the suite after each batch.
- No new test behavior, no removed coverage. Test count stays the same (145 / 128).

---

## Guard extension

`tests/architecture/test_module_size.py` `TRACKED_MODULES` expands from 3 → 6:

```
tools/builtin.py, ui/classic/terminal.py, ui/modern/app.py,    # existing
tools/agents.py, config/settings.py, llm/runner.py             # added (baselines recorded)
```

The existing `>= MODULE_SIZE_CEILING` (800) assertion is unchanged.

---

## Sequencing (lowest risk first)

1. `agents.py` (low risk, tiny blast radius) — prove the pattern.
2. `runner.py` (medium; careful monkeypatch handling).
3. `settings.py` (medium; widest surface, but well-isolated clusters).
4. Test fixtures (`conftest.py`) for modern-TUI and tools suites.
5. Extend the guard to the three new modules; full gate; validate.

## Alternatives considered

- **Split `build_function_tools` / `run_prompt_once` themselves.** Rejected: they
  are cohesive orchestrators; splitting them risks behavior drift for little gain
  since extracting the helper clusters already clears the ceiling.
- **Split the big test files by concern (Lever B).** Deferred by request — fixtures
  (Lever A) attack the root cause (duplication) and shrink files first; splitting can
  follow later if still desired.
- **A `config/` dataclass-per-file explosion.** Rejected: three cohesive submodules
  (providers / schema / io) match the existing in-repo granularity better.
