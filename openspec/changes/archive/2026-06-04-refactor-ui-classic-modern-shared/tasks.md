## 1. Shared layer

- [x] 1.1 Create `ui/shared/` with render, session, local_command, and input subpackages
- [x] 1.2 Move shared modules from top-level `ui/` and extract `SlashCommand` parsing
- [x] 1.3 Update imports across Classic, Modern, tests, and `cli.py` palette path

## 2. Modern UI

- [x] 2.1 Move `tui/` to `ui/modern/` with `render/` subpackage
- [x] 2.2 Update `cli.py` and tests (`test_app`, `test_diff`, `test_cli`)
- [x] 2.3 Remove `deepy/tui` package

## 3. Classic UI

- [x] 3.1 Move Classic modules into `ui/classic/` subpackages (prompt, status, commands, pickers)
- [x] 3.2 Regroup existing `ui/classic/*` handler modules under `commands/` and `status/`
- [x] 3.3 Update `ui/__init__.py` and Classic test monkeypatch paths

## 4. Tests and cleanup

- [x] 4.1 Reorganize non-UI tests under domain directories (`tests/llm/`, `tests/tools/`, etc.)
- [x] 4.2 Remove dead UI modules and obsolete tests
- [x] 4.3 Run `ruff`, `ty`, and full `pytest`; fix TUI skill test `discover_skills` isolation

## 5. Verification

- [x] 5.1 Confirm no remaining `deepy.tui` imports in `src/` or `tests/`
- [x] 5.2 Confirm `uv.lock` matches official PyPI when regenerated from committed `pyproject.toml`
