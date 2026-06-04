## Why

Windows users running Deepy in Windows Terminal with PowerShell 7 can hit GBK/ANSI code-page failures that do not reproduce on macOS or Linux. Python programs written by the agent can fail when they contain non-ANSI characters, file modification can fail when target files contain Unicode content encoded for Windows, and Shift+Enter may submit instead of inserting a newline.

## What Changes

- Make shell execution on Windows PowerShell 7 run Python child processes with UTF-8-safe environment defaults.
- Preserve existing macOS/Linux shell behavior and avoid applying Windows-specific encoding setup to POSIX shells.
- Teach text file tools to detect and preserve Windows GBK-compatible encodings in addition to existing UTF-8 and UTF-16LE handling.
- Keep read-before-write and stale-write protections unchanged while allowing `modify` to match Unicode text decoded from GBK-compatible files.
- Extend terminal input handling so Shift+Enter inserts a newline in Windows Terminal/PowerShell 7 while Enter continues to submit.
- Add regression coverage for PowerShell 7 command construction, Windows GBK-compatible file editing, and Windows Shift+Enter input handling.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tools`: Add requirements for Windows UTF-8-safe shell execution and GBK-compatible text file read/modify preservation.
- `runtime-environment`: Add requirements for exposing Windows encoding compatibility context without changing macOS/Linux runtime classification.
- `terminal-ui`: Add requirements for Windows Terminal Shift+Enter behavior.

## Impact

- Affected modules: `src/deepy/tools/builtin.py`, `src/deepy/tools/shell_utils.py`, `src/deepy/ui/prompt_input.py`, and possibly `src/deepy/prompts/runtime_context.py`.
- Affected tests: `tests/test_tools.py`, `tests/test_shell_utils.py`, and `tests/test_prompt_input.py`.
- No breaking CLI changes.
- No new runtime dependency is expected.
- macOS/Linux behavior should remain unchanged except for shared tests documenting that POSIX shells do not receive Windows-specific encoding mutation.
