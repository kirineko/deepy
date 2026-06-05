## MODIFIED Requirements

### Requirement: Source modules stay within the maintainable size ceiling

Tracked source modules under `src/deepy/` SHALL stay below the maintainable size
ceiling of 800 lines. A regression-guard test SHALL enforce this for the tracked
modules so the codebase cannot silently regrow oversized god-modules. The tracked
set SHALL include every module that has been decomposed to satisfy this ceiling.

#### Scenario: Tracked tool/UI/config/runtime modules are under the ceiling

- **WHEN** the module-size guard test runs over `src/deepy/`
- **THEN** `src/deepy/tools/builtin.py`, `src/deepy/ui/classic/terminal.py`,
  `src/deepy/ui/modern/app.py`, `src/deepy/tools/agents.py`,
  `src/deepy/config/settings.py`, and `src/deepy/llm/runner.py` each contain fewer
  than 800 lines
- **AND** the test passes

#### Scenario: A tracked module regrowing past the ceiling fails CI

- **WHEN** a tracked module is edited to reach or exceed 800 lines
- **THEN** the module-size guard test fails
- **AND** the failure message names the offending module and its line count

### Requirement: Oversized modules are decomposed without changing observable behavior

When an oversized module is decomposed, the change SHALL preserve all observable
behavior and the existing public and test-facing import surface. Tool outputs,
config parsing and writing, LLM turn execution, terminal and TUI rendering,
prompts, slash commands, and error messages SHALL remain identical, and existing
public import paths SHALL keep resolving.

#### Scenario: Public import surface is preserved after decomposition

- **WHEN** `src/deepy/tools/builtin.py` and `src/deepy/ui/modern/app.py` are
  decomposed into focused submodules and mixins
- **THEN** `deepy.tools.ToolRuntime`, `deepy.tools.ToolResult`, and
  `deepy.ui.modern.app.DeepyTuiApp` remain importable from their original paths
- **AND** `runtime.read(...)`, `runtime.shell(...)`, and other tool methods
  resolve and behave exactly as before

#### Scenario: Import surface of newly decomposed modules is preserved

- **WHEN** `src/deepy/tools/agents.py`, `src/deepy/config/settings.py`, and
  `src/deepy/llm/runner.py` are decomposed into focused sibling modules
- **THEN** `deepy.tools.agents.build_function_tools`,
  `deepy.tools.agents.make_mimo_compatible_tool_schema`, the full `deepy.config`
  and `deepy.config.settings` surface, and `deepy.llm.runner.run_prompt_once` /
  `RunSummary` / `DEFAULT_MAX_TURNS` / `format_deepseek_api_error` remain
  importable from their original paths
- **AND** module attributes that tests monkeypatch on `deepy.llm.runner`
  (`ensure_context_ready`, `log_debug_event`, `launch_notify_script`,
  `log_api_error`) remain patchable and take effect during a run

#### Scenario: Existing behavior tests pass unchanged after decomposition

- **WHEN** the decomposition of a tracked module is complete
- **THEN** the corresponding behavior suites pass without weakening or removing any
  assertion
- **AND** symbols those tests import from the original modules are still importable
  from those modules

## ADDED Requirements

### Requirement: High-duplication test suites obtain their harness from shared fixtures

Test suites with heavily repeated harness construction SHALL obtain that harness
from shared fixtures or helpers (for example in a `conftest.py`) rather than
duplicating construction and teardown in each test. Refactoring a suite onto shared
fixtures SHALL preserve every assertion and the suite's behavior coverage.

#### Scenario: Modern TUI suite uses a shared app harness

- **WHEN** a test in the modern TUI suite needs a running `DeepyTuiApp`
- **THEN** it obtains the app and pilot from the shared fixture/harness defined in
  the suite's `conftest.py`
- **AND** the test does not repeat the app construction and `run_test` open/close
  ritual inline

#### Scenario: Fixture migration preserves coverage

- **WHEN** a suite is migrated onto shared fixtures
- **THEN** its test count and assertions remain unchanged
- **AND** the full test suite passes
