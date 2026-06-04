## Why

Deepy's slash command suggestions are ordered by implementation category rather
than user intent, so the first view after typing `/` over-emphasizes built-in
management commands and hides subagents or skills in the Textual TUI. This makes
the command surface less discoverable just as Deepy gains more task-focused
entry points.

## What Changes

- Introduce a shared slash command discovery ranking for the stable
  prompt-toolkit UI and the experimental Textual TUI.
- Prioritize common workflow commands, task delegation commands, and currently
  relevant skills ahead of lower-frequency management or exit commands.
- Keep typed filtering responsive by ranking exact and prefix matches ahead of
  lower-confidence matches.
- Ensure the Textual TUI's bare `/` suggestion surface can reveal subagents and
  skills instead of truncating them behind the first built-in commands.
- Improve stable UI slash completions so command labels, descriptions, skill
  loaded state, and shared ranking are available consistently.
- No breaking changes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Stable prompt slash completions SHALL use intent-oriented
  ranking and include command metadata consistently.
- `experimental-textual-tui`: Textual prompt-adjacent slash suggestions and
  command discovery SHALL expose relevant commands, subagents, and skills in a
  useful order.

## Impact

- Affected code paths:
  - `src/deepy/ui/slash_commands.py`
  - `src/deepy/ui/prompt_input.py`
  - `src/deepy/tui/widgets.py`
  - `src/deepy/tui/commands.py`
  - `src/deepy/tui/app.py`
- Affected tests:
  - `tests/test_slash_commands.py`
  - `tests/test_tui_app.py`
  - Stable prompt completer tests, if added or updated.
- No dependency, file format, or external API changes.
