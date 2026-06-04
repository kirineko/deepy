## Why

Deepy now treats the Rich/prompt-toolkit UI and Textual UI as parallel system UIs.
The Rich/prompt-toolkit UI is the Classic UI, the Textual UI is the Modern UI,
and both will continue to receive UX work. The Modern UI still has several
interaction surfaces that feel noisy or hard to use: inline decisions pollute the
transcript, transcript text is hard to copy, the light theme default is not the
desired Textual theme, and management screens for skills/configuration are
visually dense but not well structured.

## What Changes

- Map the shared `light` UI theme to Textual's `solarized-light` theme by default.
- Simplify prompt action hints so the bottom prompt only shows `Esc interrupt` for interruption.
- Enable transcript text selection/copy affordances where Textual supports them.
- Move transient choice flows to a bottom interaction sheet instead of appending choice result blocks to the transcript.
- Redesign skill management as a compact one-row list with visible tabs and state-colored content.
- Redesign status/config displays into concise grouped summaries instead of mixed markdown dumps.
- Add persisted `ui.interface` selection for Classic UI vs Modern UI.
- Make the default `deepy` command enter the configured UI while keeping `deepy tui` as a Modern UI compatibility entry.
- Add `/ui` to select the default UI, and update reset/setup UI selection to offer Classic/Modern plus dark/light combinations.

## Capabilities

### New Capabilities

### Modified Capabilities

- `modern-textual-ui`: Improve Modern UI theme defaults, transcript copyability, non-polluting bottom interactions, and management screen UX.
- `terminal-ui`: Keep Classic UI and Modern UI as peer system UIs and route startup from persisted config.

## Impact

- `src/deepy/tui/theme.py`
- `src/deepy/tui/app.py`
- `src/deepy/tui/widgets.py`
- `src/deepy/tui/screens.py`
- `src/deepy/config/settings.py`
- `src/deepy/cli.py`
- `src/deepy/ui/terminal.py`
- `src/deepy/ui/slash_commands.py`
- Focused TUI tests in `tests/test_tui_app.py`
