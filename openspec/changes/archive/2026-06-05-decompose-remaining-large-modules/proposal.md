## Why

The `split-oversized-modules` change drove `builtin.py`, `terminal.py`, and
`app.py` under the 800-line ceiling and added a guard, but the guard only tracks
those three modules. Four modules still sit above the maintainable ceiling the
`code-maintainability` spec established:

- `src/deepy/tools/agents.py` — **1079 lines** (a 352-line `build_function_tools`
  builder plus ~700 lines of argument-coercion, JSON-repair, and schema-validation
  free functions)
- `src/deepy/config/settings.py` — **1070 lines** (provider catalog + predicates,
  ~10 config dataclasses with `from_mapping` parsers, and the load/write/update
  config IO family)
- `src/deepy/llm/runner.py` — **943 lines** (a 363-line `run_prompt_once`
  orchestrator plus approval, DeepSeek error-formatting, and interrupt/stream
  reconciliation helper families)

Separately, the test suite has a systemic maintainability gap that the prior
change deliberately left untouched: there is **no `conftest.py` anywhere** and the
largest suites carry **zero fixtures**, so harness setup is copy-pasted hundreds of
times. `tests/ui/modern/test_app.py` constructs `DeepyTuiApp(...)` **132 times** and
repeats the `async with app.run_test(...) as pilot:` open/close ritual **~88 times**;
`tests/tools/test_tools.py` constructs `ToolRuntime(...)` **117 times**. This makes
the suites long, noisy, and slow to change.

## What Changes

- Decompose the three remaining oversized source modules so each primary module
  drops **below 800 lines**, extracting focused sibling modules along the concern
  seams already visible in the code.
- Preserve the public and test-facing import surface for each module:
  - `deepy.tools.agents.build_function_tools` and `make_mimo_compatible_tool_schema`
  - the full `deepy.config` / `deepy.config.settings` surface (38 indirect importers
    plus direct `deepy.config.settings` importers such as `llm/provider.py`)
  - `deepy.llm.runner.run_prompt_once`, `RunSummary`, `DEFAULT_MAX_TURNS`,
    `format_deepseek_api_error`, and the module-level names tests monkeypatch
    (`ensure_context_ready`, `log_debug_event`, `launch_notify_script`, `log_api_error`)
- Extend the module-size guard's tracked set to include the three newly split
  modules so they cannot silently regrow.
- Introduce shared test harness fixtures (`conftest.py`) for the highest-duplication
  suites — a `tui_app`/`tui_harness` for the modern TUI suite and a `runtime`
  factory for the tools suite — and migrate those suites to use them. Test
  **assertions and behavior coverage stay identical**; only setup/teardown
  boilerplate moves into fixtures.
- **No observable runtime behavior change**: tool wiring, config parsing/writing,
  LLM turn execution, prompts, and error messages stay identical. This is a
  structural and test-maintainability refactor only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `code-maintainability`: expand the tracked-module set to the newly split modules,
  extend the decomposition behavior-preservation contract to their import surfaces,
  and add a requirement that high-duplication test suites obtain their harness from
  shared fixtures rather than per-test duplication.

## Impact

- **Affected source packages**:
  - `src/deepy/tools/` — `agents.py` split into `tool_args.py`, `arg_repair.py`,
    `schema_compat.py`; `agents.py` keeps `build_function_tools` + re-exports.
  - `src/deepy/config/` — `settings.py` split into `providers.py`, `schema.py`,
    `config_io.py`; `settings.py` becomes a thin re-export hub; `config/__init__.py`
    surface unchanged.
  - `src/deepy/llm/` — `runner.py` split into `runner_approvals.py`,
    `runner_errors.py`, `runner_interrupt.py`; `runner.py` keeps `run_prompt_once`
    + re-exports.
- **Affected tests**:
  - New `tests/ui/modern/conftest.py` and `tests/tools/conftest.py` with shared
    fixtures; `test_app.py` and `test_tools.py` migrated to use them.
  - `tests/architecture/test_module_size.py` tracked set expanded.
- **Public APIs**: unchanged. All current import paths keep resolving.
- **Dependencies / runtime**: none added or changed.
- **Risk**: import cycles and `ty` typing under the settings/runner splits;
  monkeypatch targets in `runner.py` must remain module attributes resolved at call
  time; test-fixture migration must not drop or weaken any assertion. Mitigated by
  per-module extraction with the full quality gate (`ruff`, `ty`, `pytest`) run
  after each step.
