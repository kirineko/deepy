## Why

Deepy users need a fast way to reference files and directories from the
interactive prompt without manually typing long relative paths. The prompt
already supports slash command completion, so adding `@` file mentions is a
natural extension of the existing terminal input workflow.

## What Changes

- Add `@`-triggered file and directory mention completion in the interactive
  prompt.
- Show top-level project files and directories when the user types `@`.
- Support narrowing and descending into paths as the user continues typing, such
  as `@src/` or `@tests/test_prompt`.
- Let Tab accept the selected file mention candidate using prompt-toolkit's
  completion behavior.
- Keep slash command completion working alongside file mention completion.
- Use an in-process, cross-platform file discovery implementation; do not depend
  on external system commands such as `rg`, `fd`, or `git`.
- Filter common generated, dependency, virtual environment, cache, and VCS
  directories from mention candidates.
- Keep all completed mentions as plain prompt text, using relative paths rooted
  at the active project directory.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `terminal-ui`: Prompt input behavior gains `@` file and directory mention
  completion.

## Impact

- `src/deepy/ui/prompt_input.py`: prompt completer composition and `@` mention
  completion integration.
- New prompt/file mention helper code for trigger parsing, file discovery,
  filtering, ranking, and caching.
- `tests/test_prompt_input.py` and focused new tests for file mention parsing,
  filtering, ranking, scoped traversal, cache behavior, and slash completion
  coexistence.
- No new runtime dependency on external binaries or platform-specific shell
  tools.
