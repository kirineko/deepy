## Why

Deepy currently exposes Windows only as raw runtime context while its shell tool,
tool documentation, and command guidance still assume POSIX-style bash or zsh.
On Windows, especially in PowerShell sessions, this makes DeepSeek more likely to
return Linux/macOS commands or trigger POSIX-only shell wrappers that do not match
the user's actual environment.

## What Changes

- Add first-class runtime environment awareness for OS family, shell kind,
  command dialect, and path style.
- Teach the system prompt and tool documentation to prefer commands that match
  the detected user environment, including Windows PowerShell.
- Rename the model-facing shell execution tool to `shell`.
- Add PowerShell-aware command wrapping so Windows sessions can preserve cwd,
  capture exit status, and report metadata without POSIX-only syntax.
- Preserve existing bash/zsh behavior on Linux and macOS.
- Add tests for environment classification, prompt/tool guidance, POSIX shell
  compatibility, and PowerShell command construction.

## Capabilities

### New Capabilities

- `runtime-environment`: detection and prompt exposure of the user's operating
  system, shell, command dialect, and path style.

### Modified Capabilities

- `tools`: shell execution changes from POSIX-centric bash assumptions to a
  cross-platform shell executor that supports Windows PowerShell while preserving
  existing Linux/macOS behavior.

## Impact

- Affected code:
  - `src/deepy/prompts/runtime_context.py`
  - `src/deepy/prompts/system.py`
  - `src/deepy/prompts/tool_docs.py`
  - `src/deepy/data/tools/shell.md`
  - `src/deepy/tools/agents.py`
  - `src/deepy/tools/builtin.py`
  - `src/deepy/tools/shell_utils.py`
- Affected tests:
  - runtime context and system prompt tests
  - shell utility tests
  - shell tool execution and metadata tests
  - function tool description/schema tests
- No breaking CLI change is expected. New model sessions use the `shell` tool.
