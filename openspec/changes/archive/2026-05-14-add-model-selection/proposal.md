## Why

Deepy currently defaults to `deepseek-v4-pro` with thinking enabled at `max`,
but users cannot change model or thinking behavior from the interactive session.
DeepSeek now exposes both V4 Flash and V4 Pro with explicit thinking-mode
controls, so Deepy should make those choices easy without requiring users to
edit TOML by hand.

## What Changes

- Add a DeepSeek model catalog for supported model choices, starting with
  `deepseek-v4-pro` and `deepseek-v4-flash`.
- Extend model configuration so users can persist the selected model and
  thinking strength while remaining compatible with existing `[model]` fields.
- Interpret `none` as thinking disabled, and interpret `high`/`max` as thinking
  enabled with the matching `reasoning_effort`.
- Add an interactive `/model` command that favors keyboard selection over free
  text input.
- Let users pick a model first, then immediately pick thinking strength
  `none`, `high`, or `max`.
- Keep direct command forms for scripting and fast terminal use, such as setting
  the model or reasoning mode by argument.
- Update status, welcome, help, and documentation surfaces so the active model
  and thinking mode are clear.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `configuration`: persistent TOML configuration gains validated model choice
  and unified reasoning-mode semantics while preserving existing config fields.
- `deepseek-provider`: provider settings map the saved reasoning mode to
  DeepSeek's OpenAI-compatible thinking parameters.
- `terminal-ui`: interactive slash commands gain a selectable `/model` flow for
  model and thinking-strength changes.

## Impact

- Affected code:
  - `src/deepy/config/settings.py`
  - `src/deepy/llm/thinking.py`
  - `src/deepy/llm/provider.py`
  - `src/deepy/ui/slash_commands.py`
  - `src/deepy/ui/terminal.py`
  - `src/deepy/ui/welcome.py`
  - `src/deepy/status.py`
  - `src/deepy/cli.py`
- Affected tests:
  - config parsing and targeted config update tests
  - provider/model-settings tests
  - interactive slash-command tests
  - welcome/status/help rendering tests
  - README/config documentation checks if present
- No new runtime dependency is expected. The implementation should use existing
  TOML, Rich, prompt-toolkit, and current DeepSeek/OpenAI SDK provider paths.
