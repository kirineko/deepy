## Context

Deepy ships two terminal interfaces:

- **Classic** (`prompt_toolkit`) — `deepy.ui.classic`
- **Modern** (Textual) — `deepy.ui.modern`

Both depended on many modules that lived at `deepy/ui/*.py` or `deepy/tui/*` without
a clear shared layer. Modern imported Classic-adjacent paths even when the code was
UI-agnostic (rendering, sessions, slash commands, local commands).

## Goals

- Enforce `classic → shared` and `modern → shared` only; no `modern ↔ classic`.
- Keep public entry points stable: `deepy`, `deepy.ui`, `deepy.cli`.
- Split legacy cores (`classic/terminal.py`, `modern/app.py`) only where handlers
  were self-contained and test patches could move cleanly.
- Mirror structure in `tests/` for discoverability.

## Non-Goals

- Changing slash-command semantics, TUI screens, or transcript rendering behavior.
- Splitting `DeepyTuiApp` or `run_interactive` into mixins in this change.
- OpenSpec requirement edits (no user-visible contract change).

## Decisions

### Package layout

```
deepy/ui/
  shared/     # render, session, local_command, input, model_picker
  classic/    # terminal, markdown, prompt/, status/, commands/, pickers/
  modern/     # app, runner, render/, widgets/, screens/
```

### Slash commands

`SlashCommand` and `parse_slash_command` move to `shared/input/commands.py` so
Modern and Classic share one parser without importing `terminal.py`.

### `deepy/tui` removal

All Textual code moves to `deepy/ui/modern/`. CLI imports `deepy.ui.modern.run_tui`.

### Tests

Tests move to `tests/ui/{shared,classic,modern}/...` and domain folders
(`tests/llm/`, `tests/tools/`, etc.). String-based `monkeypatch.setattr` targets
update to new module paths.

## Risks / Trade-offs

- Large diff surface; mitigated by mechanical moves and full pytest suite.
- Contributors with muscle memory for `deepy.tui.*` must use `deepy.ui.modern.*`.
- Legacy cores remain large but are now surrounded by focused modules.

## Migration Plan

- Use `uv run deepy` from the repo for development; `import deepy` paths unchanged
  at the package root.
- Update any external forks that imported `deepy.tui` directly to `deepy.ui.modern`.

## Open Questions

- None.
