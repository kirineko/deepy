## Why

Deepy currently uses fixed terminal colors that are readable in dark themes but
can lose contrast in light-background terminals, making muted text, panels,
diff previews, and status output hard to read. Users need a predictable way to
choose a readable UI theme on first launch and to change that choice later.

## What Changes

- Add terminal UI theme support with at least `dark`, `light`, and `auto`
  choices.
- Apply theme-aware colors across the welcome screen, message panels, status
  lines, prompt/user text, thinking/progress output, tool output, and diff/write
  previews.
- Prompt users to choose a theme during first interactive startup when no UI
  theme has been saved.
- Persist the selected theme in Deepy's TOML configuration.
- Add commands to inspect and change the saved UI theme after setup.
- Keep existing dark-terminal behavior as the default-compatible experience for
  users who already have config files and do not change the setting.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: terminal rendering becomes theme-aware, including startup theme
  selection and readable output in light and dark terminal backgrounds.
- `configuration`: persistent TOML configuration gains a UI theme setting and
  commands for reading/updating it.

## Impact

- Affected code:
  - `src/deepy/ui/styles.py`
  - `src/deepy/ui/welcome.py`
  - `src/deepy/ui/message_view.py`
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/prompt_input.py`
  - `src/deepy/config/settings.py`
  - `src/deepy/cli.py`
- Affected tests:
  - terminal UI rendering tests
  - welcome rendering tests
  - message/diff preview tests
  - config parsing and setup/init command tests
  - slash or CLI command tests for theme inspection and update
- No new runtime dependency is expected. The implementation should use existing
  Rich, prompt-toolkit, and TOML configuration paths.
