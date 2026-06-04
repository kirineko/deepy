## Why

The Classic (`prompt_toolkit`) and Modern (Textual) UI code had grown into large,
flat modules (`terminal.py`, `tui/app.py`, and many top-level `ui/*.py` files).
Maintainers needed clearer boundaries, smaller files, and a strict dependency
direction so shared primitives are not trapped inside Classic-only paths.

## What Changes

- Reorganize `deepy/ui/` into three peer packages: `classic/`, `modern/`, and
  `shared/`, with concern-based subpackages (commands, prompt, status, render,
  session, input, widgets, screens).
- Remove the standalone `deepy/tui` package; Modern UI lives under
  `deepy/ui/modern/`.
- Extract shared slash-command parsing (`SlashCommand`, `parse_slash_command`)
  into `ui/shared/input/commands.py`.
- Split oversized modules into focused helpers (message render stack, skill
  commands, config commands, TUI widgets/screens, and related test modules).
- Remove dead/orphan UI modules and test-only surfaces uncovered during the
  refactor.
- Reorganize tests under `tests/ui/`, `tests/llm/`, `tests/tools/`, and other
  mirrors of source layout.
- Preserve all user-visible CLI/TUI behavior, public entry points (`deepy`,
  `deepy.ui.run_interactive`, `deepy.ui.modern.run_tui`), and existing import
  compatibility at the `deepy.ui` package boundary.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: document Classic UI living under `deepy.ui.classic` with shared
  helpers in `deepy.ui.shared` (no user-visible behavior change).
- `experimental-textual-tui`: document Modern UI living under `deepy.ui.modern`
  and removal of `deepy.tui` (no user-visible behavior change).

## Impact

- `src/deepy/ui/**`, removal of `src/deepy/tui/**`
- `src/deepy/cli.py` import paths
- `tests/**` layout and monkeypatch string targets for moved modules
- `AGENTS.md` focused-test examples
- No OpenSpec canonical requirement updates; no PyPI version or user-doc changes
  required for this change alone.
