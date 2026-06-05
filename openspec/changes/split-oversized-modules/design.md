## Context

Three source modules exceed 2,000 lines and concentrate many unrelated concerns:

| Module | Lines | Dominant shape |
| --- | --- | --- |
| `src/deepy/tools/builtin.py` | 3846 | `ToolRuntime` dataclass (~1,557 lines, 26 methods) + ~2,200 lines of free functions |
| `src/deepy/ui/classic/terminal.py` | 2697 | ~40 free functions + small worker/renderer classes |
| `src/deepy/ui/modern/app.py` | 2632 | `DeepyTuiApp(App[None])` god-class (~2,189 lines, ~110 methods) + module helpers |

`AGENTS.md` governance: new modules ≤300 lines preferred, >400 is a review
warning, >600 is a legacy boundary that should not accrete new behavior, and no
new module should exceed 1,000 lines. The repo already contains the target-shape
packages (`tools/search.py`, `tools/shell_output.py`, `ui/classic/commands/`,
`ui/classic/status/`, `ui/modern/render/`, `ui/modern/screens/`), so this is a
"follow the existing pattern" decomposition.

Coupling that constrains the approach (measured, not assumed):

- `deepy.tools.ToolRuntime` / `ToolResult` are re-exported from
  `tools/__init__.py` and consumed by `tools/agents.py`, `llm/runner.py`, tests.
  Tool methods are invoked as bound methods / `getattr(runtime, name)`.
- `tests/tools/test_tools.py` imports private constants from
  `deepy.tools.builtin` (e.g. `DEFAULT_LINE_LIMIT`, `MAX_BASH_OUTPUT_CHARS`,
  `MAX_LINE_LENGTH`, ...).
- `tests/ui/classic/test_terminal.py` imports ~14 private functions from
  `deepy.ui.classic.terminal` (`_handle_slash_command`, `_print_assistant_output`,
  `_print_stream_event`, `_print_user_input`, `_build_status_footer`,
  `_format_context_footer`, `_print_usage_footer`, `_run_once_with_status`,
  `_collect_pending_question_response`, `_format_duration_ms`,
  `_format_stream_token_count_short`, `_format_token_count_short`,
  `_tool_output_text`, `_working_status_text`).
- `ui/classic/__init__.py` imports `run_interactive`; `config_commands.py` /
  `model_commands.py` import the `InputFunc` type alias from `terminal`.
- `tests/ui/modern/test_app.py` imports only `DeepyTuiApp` (low coupling).
- `ui/modern/commands.py` and `ui/modern/runner.py` import `DeepyTuiApp` from
  `deepy.ui.modern.app`.

## Goals / Non-Goals

**Goals:**
- Bring each of the three primary modules **below 800 lines**.
- Preserve 100% of observable behavior (tool outputs, rendering, prompts, slash
  commands, error text) and the existing public/test import surface.
- Land the work as small, independently reviewable, test-green steps.
- Add a regression guard so tracked modules cannot silently regrow.

**Non-Goals:**
- No logic/behavior changes, no bug fixes, no output wording changes bundled in.
- Not shrinking the large test files (`test_app.py`, `test_terminal.py`,
  `test_tools.py`) — they are the safety net and out of scope here.
- Not redesigning tool dispatch, the Textual app lifecycle, or the agent loop.
- Not chasing ≤300 lines for every extracted file in one pass; ≤800 for the
  primary modules is the hard target, ≤400 the aspiration for new files.

## Decisions

### D1 — God-classes are decomposed via concern-grouped mixins (not free functions)

`ToolRuntime` and `DeepyTuiApp` are split into mixin classes, one focused module
per concern, then reassembled:

```python
@dataclass
class ToolRuntime(
    ReadToolsMixin, MutationPreflightMixin, MutationApplyMixin,
    ShellToolsMixin, TaskToolsMixin, WebToolsMixin, InteractionToolsMixin,
):
    cwd: Path
    settings: Settings
    ...  # all dataclass fields stay on the concrete class
```

Rationale: mixins keep every method a bound instance method, so `runtime.read(...)`,
`getattr(runtime, "shell")`, and Textual's `on_*` / `action_*` handler discovery
all keep working unchanged. Converting methods to free functions would change
call sites and break the public surface.

*Alternative considered*: extract free functions and make methods thin wrappers.
Rejected — doubles the surface (wrapper + function) and still leaves large
wrapper bodies; higher churn at call sites.

### D2 — Mixins type shared state through a non-dataclass state base

Mixins reference `self.cwd`, `self.settings`, `self.file_state`, etc. To satisfy
`ty` without redeclaring dataclass fields, introduce a typing-only base that
declares attribute annotations (no defaults, not a dataclass), e.g.
`tools/runtime/state.py: class ToolRuntimeState` and
`ui/modern/app_state_proto` (or reuse `TuiState` ownership). Mixins inherit the
state base for type visibility; the concrete `@dataclass ToolRuntime` owns the
real fields. The state base must NOT declare `field(default_factory=...)` (that
stays on the dataclass) to avoid double-definition.

*Alternative considered*: `typing.Protocol` + `cast`. Equivalent; a shared base in
the MRO is simpler for instance attribute access and avoids per-method casts.

### D3 — Free-function clusters move to focused sibling modules; originals keep re-exports

Module-level functions move to focused modules; the primary module re-imports the
names used by the public API and by tests so the import surface is unchanged.
This keeps `tests/ui/classic/test_terminal.py` and `tests/tools/test_tools.py`
green with zero test edits.

Layering rule to avoid cycles: leaf modules never import the primary module;
the primary module imports leaf modules at the bottom; truly shared constants and
helper dataclasses live in their own leaf module (`tools/constants.py`,
`tools/payloads.py`) imported by both.

### D4 — Target module layout per file

**`tools/builtin.py` 3846 → ~200** (dataclass + `__post_init__` + mixin assembly
+ re-exports). New modules:

| New module | From lines | ~Lines |
| --- | --- | --- |
| `tools/constants.py` | header consts (1–120) | ~60 |
| `tools/payloads.py` | frozen dataclasses (374–470) | ~100 |
| `tools/mutation_policy.py` | path/mutation policy (121–372) | ~250 |
| `tools/text_match.py` | fuzzy/closest match (476–675) | ~200 |
| `tools/text_io.py` | diff/encoding/atomic write (2755–2930) | ~176 |
| `tools/payload_parsing.py` | v3 read/update parse, notebook (2932–3122) | ~190 |
| `tools/media.py` | pdf/image (3124–3260) | ~137 |
| `tools/shell_command.py` | line endings/truncate/shell build (3261–3846) | ~430 (may sub-split) |
| `tools/web/query.py` | query prep + LLM (681–833) | ~153 |
| `tools/web/search_parse.py` | DuckDuckGo/searxng parse (840–1000) | ~161 |
| `tools/web/fetch_html.py` | readable HTML extract (1004–1196) | ~193 |
| `tools/runtime/state.py` | typing state base | ~40 |
| `tools/runtime/read.py` | `_read_file_result`, `read` | ~210 |
| `tools/runtime/mutation_preflight.py` | `preflight_*`, `_plan_update_file` | ~350 |
| `tools/runtime/mutation_apply.py` | `_write_result`, `write_v3`, `update` | ~350 |
| `tools/runtime/shell.py` | `shell`, `test_shell`, background helpers | ~200 |
| `tools/runtime/tasks.py` | `task_list/output/stop` | ~70 |
| `tools/runtime/web.py` | `web_search/web_fetch/_web_search_builtin/...` | ~330 |
| `tools/runtime/interaction.py` | `search`, `ask_user_question`, `todo_write`, `load_skill` | ~110 |

**`ui/classic/terminal.py` 2697 → ~500** (keeps `run_interactive`,
`_run_once_with_status`, `InputFunc` alias, and re-exports for tested helpers).
New sibling modules in `ui/classic/`:

| New module | From lines | ~Lines |
| --- | --- | --- |
| `runtime_workers.py` | worker/bridge/startup-state classes (211–373) | ~162 |
| `startup.py` | version check/theme/prompt session/mcp/suggestion (762–940) | ~180 |
| `approvals.py` | approval resolver/preflight/local command (1054–1275) | ~220 |
| `esc_watch.py` | ESC watchers + background stop/cleanup (1275–1397) | ~120 |
| `stream_render.py` | `TerminalStreamRenderer` + inline/silent status (1397–1585, 2272–2325) | ~240 |
| `slash_commands.py` | slash/compact/resume/history (1585–1940) | ~355 |
| `exit_summary.py` | exit summary + session cost (1940–2021) | ~120 |
| `footer.py` | toolbar/status footer/context/usage + token format helpers (2021–2272) | ~250 |
| `printing.py` | print user/assistant/stream/tool debug (2325–2595) | ~270 |
| `questions.py` | question collect/prompt (2595–end) | ~110 |

**`ui/modern/app.py` 2632 → ~400** (keeps `DeepyTuiApp` class header, `BINDINGS`,
`CSS`, `COMMANDS`, reactive `state`, `__init__`, `compose`, `on_mount`, top-level
`action_*`/`on_*` lifecycle, and re-export). To avoid a `app.py`-vs-`app/`
name clash, mixins live in flat sibling modules:

| New module | Concern | ~Lines |
| --- | --- | --- |
| `app_commands.py` | `_run_tui_command`, help/status, theme/ui/model/view/reset/suggestion | ~520 (may sub-split reset) |
| `app_skills.py` | all `_skills_*` + skill screen handlers | ~310 |
| `app_streaming.py` | `run_model_turn`, `on_stream_event`, `_handle_stream_event` | ~250 |
| `app_transcript.py` | append/replace/insert/restore transcript, assistant delta, scroll | ~300 |
| `app_interaction.py` | approval resolver, tool blocks, inline choice, question, sheet | ~400 |
| `app_status.py` | status bar/context, session-entry cache, session cost, exit summary | ~330 |
| `app_sessions.py` | new/show/resume/choose/compact session, background tasks | ~250 |
| `app_helpers.py` | module-level helpers (2453–2632) | ~180 |

### D5 — Sequencing: lowest risk first

1. **`terminal.py`** first — mostly free functions, easiest, exercises the
   re-export + cycle discipline on the most test-coupled file.
2. **`builtin.py`** next — free-function moves first (mechanical), then the
   `ToolRuntime` mixin split.
3. **`app.py`** last — the highest-risk god-class split (Textual lifecycle).

Each module extraction is its own commit; the full gate runs after each.

### D6 — Regression guard test

Add `tests/architecture/test_module_size.py` that walks `src/deepy/**/*.py` and
asserts tracked modules stay under the ceiling (hard fail >800 for the three
former offenders; optional soft list for >600 new files). This satisfies the
`code-maintainability` requirement and prevents silent regrowth.

## Risks / Trade-offs (watch-points)

- **[Test import coupling — terminal.py]** ~14 private functions are imported by
  `test_terminal.py`. → Re-export every moved-and-tested symbol from
  `terminal.py` (`from .footer import _build_status_footer, ...`). Verify the
  exact list before deleting originals; run `tests/ui/classic/test_terminal.py`
  after each move.
- **[Test import coupling — builtin.py]** private constants imported by
  `test_tools.py`. → Keep constants in `tools/constants.py` and re-export from
  `builtin.py`; confirm the full imported set (the test import block is
  multi-line) before moving.
- **[dataclass + mixin typing under `ty`]** mixins touching `self.<field>` can
  trip `ty`. → Shared non-dataclass state base (D2); keep `field(...)` only on
  the concrete dataclass; run `uv run ty check src` after each extraction.
- **[Import cycles]** leaf modules importing the primary module, or
  runtime mixins importing `builtin.ToolRuntime`. → Strict layering: mixins
  import only `runtime/state.py` + helper leaf modules, never `builtin`;
  `tools/__init__.py` imports `builtin` last; shared consts/dataclasses in their
  own leaf modules.
- **[Textual handler discovery]** `on_*`/`action_*` must remain discoverable
  after moving to mixins. They are inherited into the class namespace via MRO, so
  this should hold, but `compose`, reactive `state: var`, `BINDINGS`, `CSS`,
  `COMMANDS` MUST stay on the concrete `DeepyTuiApp`. → Keep lifecycle/class-vars
  on the concrete class; smoke-run `tests/ui/modern/test_app.py` after the split.
- **[Shared private helpers across mixins]** e.g. `_read_file_result` (read),
  `_plan_update_file`/`_write_result` (mutation). → Co-locate each helper with
  its primary caller; cross-mixin calls resolve via `self` at runtime and via the
  state base for typing.
- **[Module vs package name clash]** an `app/` package cannot coexist with
  `app.py`. → Keep `app.py` and use flat `app_*.py` sibling modules (D4); same
  for `builtin.py` + `tools/runtime/` (different names, no clash).
- **[Platform-semantics tests]** shell/encoding/line-ending logic moves to
  `tools/shell_command.py` / `tools/text_io.py`. → Preserve behavior exactly and
  keep Windows/PowerShell/CRLF tests passing; re-export any symbols those tests
  import.
- **[New packages need `__init__.py`]** `tools/runtime/`, `tools/web/`,
  `tests/architecture/`. → Add them; export nothing unexpected.
- **[Diff discipline]** mixing a behavior tweak into a move would defeat the
  safety argument. → Pure moves only; if a real bug is found, file it separately.

## Migration Plan

1. Land `code-maintainability` spec + the module-size guard test first (guard may
   start in "report-only" mode if needed, then flip to hard-fail once all three
   modules are under 800).
2. Refactor `terminal.py` module-by-module (workers → startup → approvals →
   esc_watch → stream_render → slash_commands → exit_summary → footer → printing
   → questions), adding re-exports; run `ruff` + `ty` + `tests/ui/classic` after
   each.
3. Refactor `builtin.py`: move free-function clusters (constants/payloads/
   policy/text_match/text_io/payload_parsing/media/shell_command/web/*), then
   split `ToolRuntime` into the `runtime/` mixins; run `ruff` + `ty` +
   `tests/tools` after each.
4. Refactor `app.py` into `app_*` mixins + `app_helpers`; run `ruff` + `ty` +
   `tests/ui/modern` after each.
5. Flip the size guard to hard-fail; run the full suite (`uv run pytest`,
   `uv run ruff check src tests`, `uv run ty check src`).

**Rollback**: each step is an isolated commit; revert the offending commit. The
public surface and tests are unchanged throughout, so partial completion still
leaves a working tree.

## Open Questions

- Should the size guard hard-fail threshold be exactly 800, or a slightly higher
  safety margin (e.g. 850) to avoid churn on near-boundary edits? (Proposed: 800
  for the three tracked modules; broad soft warning at 600 for new files.)
- Should test-import migration (pointing tests at the new module paths) happen in
  this change or a follow-up? (Proposed: keep re-exports now, migrate later to
  keep this diff minimal.)
- `tools/shell_command.py` (~430) and `app_commands.py` (~520) may still exceed
  the 400 aspiration — sub-split now or accept as documented follow-up?
