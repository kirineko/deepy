## 1. Local Command Display

- [x] 1.1 Hide `exit 0` metadata for successful Modern UI local commands.
- [x] 1.2 Keep non-zero exit code metadata visible for failed local commands.
- [x] 1.3 Add focused tests for success and failure metadata rendering.

## 2. Bottom-Sheet Pickers

- [x] 2.1 Add explicit readable styles for bottom-sheet `OptionList` controls.
- [x] 2.2 Cover inline provider/model-style choices with a regression test.
- [x] 2.3 Audit related bottom-sheet components that use `OptionList`.

## 3. Validation

- [x] 3.1 Validate this OpenSpec change in strict mode.
- [x] 3.2 Run focused Modern UI tests.
- [x] 3.3 Run `uv run ruff check src tests`, `uv run ty check src`, and `git diff --check`.
