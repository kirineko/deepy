## Why

Deepy's current rule loading is too shallow: it reads only the project root `AGENTS.md` and `~/.deepy/AGENTS.md`, without directory scoping, precedence semantics, size limits, or strong prompt guidance. Since this feature has not been formally used, now is the right time to replace the early implementation with a clean Agent-instruction model instead of preserving legacy behavior.

## What Changes

- Standardize Deepy's project instruction file name on `AGENTS.md`.
- Keep Deepy-specific global instructions at `~/.deepy/AGENTS.md`.
- Load project `AGENTS.md` files hierarchically from the git project root to the current working directory.
- Treat deeper project files as more specific than parent files, while direct user instructions still take precedence over all loaded instruction files.
- Add source annotations and a bounded instruction budget so loaded rules remain auditable and do not consume unbounded context.
- Strengthen the system prompt so `AGENTS.md` content is treated as binding project and user guidance unless it conflicts with higher-priority instructions.
- Add an interactive `/init` slash command that asks the agent to analyze the current repository and create or update the project root `AGENTS.md`.
- Remove the old fixed-root-only behavior; no compatibility is required for alternate file names or non-standard global locations.

## Capabilities

### New Capabilities

- `agent-instructions`: Covers Deepy's discovery, ordering, precedence, prompt injection, and maintenance behavior for `AGENTS.md` instructions.

### Modified Capabilities

- None.

## Impact

- Affected code:
  - `src/deepy/prompts/rules.py`
  - `src/deepy/prompts/init_agents.py`
  - `src/deepy/prompts/system.py`
  - `src/deepy/ui/slash_commands.py`
  - `src/deepy/ui/terminal.py`
  - prompt-related tests in `tests/test_prompts.py`
  - terminal/slash-command tests in `tests/test_slash_commands.py` and `tests/test_terminal_ui.py`
  - user documentation in `README.md` and `README.zh-CN.md`
- No new runtime dependency is expected.
- This is a behavioral cleanup for an immature feature; users should use `~/.deepy/AGENTS.md` for Deepy-wide preferences and project `AGENTS.md` files for repository or subdirectory guidance.
