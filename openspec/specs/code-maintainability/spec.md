# code-maintainability Specification

## Purpose
TBD - created by archiving change split-oversized-modules. Update Purpose after archive.
## Requirements
### Requirement: Source modules stay within the maintainable size ceiling

Tracked source modules under `src/deepy/` SHALL stay below the maintainable size
ceiling of 800 lines. A regression-guard test SHALL enforce this for the
previously oversized modules so the codebase cannot silently regrow oversized
god-modules.

#### Scenario: Tracked tool/UI modules are under the ceiling

- **WHEN** the module-size guard test runs over `src/deepy/`
- **THEN** `src/deepy/tools/builtin.py`, `src/deepy/ui/classic/terminal.py`, and
  `src/deepy/ui/modern/app.py` each contain fewer than 800 lines
- **AND** the test passes

#### Scenario: A tracked module regrowing past the ceiling fails CI

- **WHEN** a tracked module is edited to exceed 800 lines
- **THEN** the module-size guard test fails
- **AND** the failure message names the offending module and its line count

### Requirement: Oversized modules are decomposed without changing observable behavior

When an oversized module is decomposed, the change SHALL preserve all observable
behavior and the existing public and test-facing import surface. Tool outputs,
terminal and TUI rendering, prompts, slash commands, and error messages SHALL
remain identical, and existing public import paths SHALL keep resolving.

#### Scenario: Public import surface is preserved after decomposition

- **WHEN** `src/deepy/tools/builtin.py` and `src/deepy/ui/modern/app.py` are
  decomposed into focused submodules and mixins
- **THEN** `deepy.tools.ToolRuntime`, `deepy.tools.ToolResult`, and
  `deepy.ui.modern.app.DeepyTuiApp` remain importable from their original paths
- **AND** `runtime.read(...)`, `runtime.shell(...)`, and other tool methods
  resolve and behave exactly as before

#### Scenario: Existing behavior tests pass unchanged after decomposition

- **WHEN** the decomposition of a tracked module is complete
- **THEN** `tests/tools/test_tools.py`, `tests/ui/classic/test_terminal.py`, and
  `tests/ui/modern/test_app.py` pass without edits to their assertions
- **AND** symbols those tests import from the original modules are still
  importable from those modules

