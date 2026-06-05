## Why

Three source modules have grown into oversized god-objects that violate the
module-size governance in `AGENTS.md` (new modules should stay ≤300 lines, >600
lines is a legacy review boundary, and no new module should exceed 1,000 lines):

- `src/deepy/tools/builtin.py` — **3846 lines** (a 1,557-line `ToolRuntime`
  class plus ~2,200 lines of free functions)
- `src/deepy/ui/classic/terminal.py` — **2697 lines** (free-function sprawl plus
  a few helper classes)
- `src/deepy/ui/modern/app.py` — **2632 lines** (a 2,189-line `DeepyTuiApp`
  god-class)

These files are hard to read in one pass, hard to review, and concentrate
unrelated concerns (file mutation, web fetch, shell, PDF parsing, stream
rendering, slash commands, status footers, etc.) in a single unit. They each
already have rich sibling packages (`tools/`, `ui/classic/commands/`,
`ui/modern/render/`) that demonstrate the target structure, so decomposition
follows an established in-repo pattern rather than inventing one.

## What Changes

- Decompose each of the three modules so that the primary module drops **below
  800 lines**, extracting focused submodules along the natural concern seams
  already visible in the code.
- For the two god-classes (`ToolRuntime`, `DeepyTuiApp`), split methods into
  concern-grouped mixin modules and reassemble the original class so its public
  surface is byte-for-byte identical to callers.
- Move clusters of module-level free functions into focused sibling modules
  (path/mutation policy, fuzzy matching, web search/fetch parsing, shell command
  construction, stream rendering, slash commands, status/footer, printing,
  question prompting, etc.).
- Preserve the public import surface: `deepy.tools.ToolRuntime`,
  `deepy.tools.ToolResult`, and `DeepyTuiApp` / `run_interactive` entry points
  keep their current import paths and behavior.
- Add a regression-guard test that fails if a tracked source module exceeds the
  agreed line ceiling, so the codebase does not silently regrow oversized files.
- **No observable behavior change**: tool outputs, CLI/TUI rendering, prompts,
  slash commands, and error messages stay identical. This is a structural
  refactor only.

## Capabilities

### New Capabilities

- `code-maintainability`: Governs source-module size limits and the requirement
  that oversized modules be decomposed without changing observable behavior,
  with a regression guard that keeps tracked modules under the ceiling.

### Modified Capabilities

None. No requirement-level (observable) behavior changes; the refactor preserves
all existing tool, terminal-ui, and experimental-textual-tui contracts.

## Impact

- **Affected source packages**:
  - `src/deepy/tools/` — `builtin.py` split into mutation/text-match/web/media/
    shell-command helper modules plus a `tools/runtime/` mixin package.
  - `src/deepy/ui/classic/` — `terminal.py` split into runtime workers, startup,
    approvals, esc-watch, stream render, slash commands, footer, printing, and
    questions modules.
  - `src/deepy/ui/modern/` — `app.py` split into a `ui/modern/app/` mixin package
    plus an `app_helpers` module.
- **Public APIs**: unchanged. `deepy.tools.ToolRuntime`/`ToolResult` and the
  modern/classic UI entry points keep their import paths.
- **Tests**: existing suites (`tests/tools/test_tools.py`,
  `tests/ui/classic/test_terminal.py`, `tests/ui/modern/test_app.py`) act as the
  behavior-preservation net; one new module-size guard test is added.
- **Dependencies / runtime**: none added or changed.
- **Risk**: regression risk from moving code across module boundaries (import
  cycles, dataclass + mixin typing under `ty`); mitigated by per-module
  extraction with the full quality gate run after each step.
