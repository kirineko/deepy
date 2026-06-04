## Why

Deepy can make follow-up turns faster by suggesting the user's likely next input
after a model response completes. This should be available in both the stable
terminal UI and the experimental Textual TUI without changing Enter-to-submit
behavior or hiding the extra model usage it creates.

## What Changes

- Add input suggestions that appear as ghost text in the prompt after eligible
  assistant replies.
- Generate suggestions only after at least two model replies in the active
  session and only when no model turn, local command, or user-confirmation flow
  is active.
- Accept visible suggestions with Tab or Right Arrow by inserting the suggestion
  into the input buffer; Enter SHALL NOT accept or submit a suggestion.
- Dismiss suggestions when the user starts typing, pastes content, submits a
  prompt, starts a new model turn, or toggles the feature off.
- Use a fixed background suggestion model: `deepseek-v4-flash` with DeepSeek
  thinking disabled. Users cannot customize this model in this change.
- Enable input suggestions by default and add `/input-suggestion` as a no-arg
  slash command that toggles the feature on or off for the active persisted
  configuration.
- Record suggestion model usage separately from ordinary turn usage and context
  window accounting.
- Add quality filters so low-value, overly long, evaluative, AI-voiced,
  formatted, error-like, or meta suggestions are suppressed.

## Capabilities

### New Capabilities
- `input-suggestions`: covers suggestion generation, visibility, acceptance,
  dismissal, model selection, filtering, and separate usage accounting.

### Modified Capabilities
- `terminal-ui`: stable prompt-toolkit UI SHALL render and accept ghost-text
  input suggestions and expose `/input-suggestion`.
- `experimental-textual-tui`: Textual prompt UI SHALL attempt an in-input
  ghost-text experience with the same acceptance and dismissal semantics.
- `configuration`: local TOML settings SHALL persist the input suggestion
  enabled state with a default of enabled.
- `deepseek-provider`: background input suggestion calls SHALL use
  `deepseek-v4-flash` with thinking disabled and SHALL not inherit the active
  reasoning mode.
- `session-context`: suggestion usage SHALL be accounted separately from
  ordinary model-turn token usage and context window checkpoints.

## Impact

- Affected code areas include `src/deepy/config/settings.py`,
  `src/deepy/llm/provider.py`, `src/deepy/llm/thinking.py`,
  `src/deepy/ui/prompt_input.py`, `src/deepy/ui/terminal.py`,
  `src/deepy/ui/slash_commands.py`, `src/deepy/tui/widgets.py`,
  `src/deepy/tui/app.py`, session usage persistence, and related tests.
- The change adds a small background model-call path for interactive sessions.
- No breaking change is intended for prompt submission, slash command parsing,
  main model selection, reasoning configuration, local command mode, or existing
  completion surfaces.
