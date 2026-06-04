## Why

Windows users can receive mojibake from shell tool output when native commands such
as `wsl.exe --status` emit non-UTF-8 bytes through PowerShell. Separately,
multiline prompt input still depends on platform-specific shortcut behavior, and
user testing showed Ctrl+Enter and Shift+Enter are not reliable enough across
common terminals; Ctrl+J should be the single newline shortcut.

## What Changes

- Decode shell stdout and stderr from captured bytes with Windows-compatible
  fallbacks so native command output remains readable without asking users to run
  `chcp` or edit their PowerShell profile.
- Keep existing PowerShell wrapper behavior for cwd tracking, exit-code tracking,
  Python UTF-8 defaults, timeout handling, and shell metadata.
- Make prompt input support Ctrl+J as the user-facing newline shortcut on all
  platforms while preserving Enter submission.
- Remove Shift+Enter and Ctrl+Enter prompt newline handling so there is only one
  documented multiline shortcut.
- Add focused regression tests for Windows shell output decoding and cross-platform
  Ctrl+J multiline input.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tools`: Shell execution output decoding must tolerate Windows native command
  encodings while preserving the existing shell result contract.
- `terminal-ui`: Prompt multiline input must support Ctrl+J consistently without
  Shift+Enter or Ctrl+Enter newline guidance.

## Impact

- Affected code: `src/deepy/tools/builtin.py`, `src/deepy/ui/prompt_input.py`,
  shell tool documentation, and related tests.
- Affected specs: `openspec/specs/tools/spec.md` and
  `openspec/specs/terminal-ui/spec.md`.
- No tool schema, CLI command, configuration, session format, or dependency
  changes are expected.
- Non-goal: keep advertising or supporting Shift+Enter or Ctrl+Enter as newline
  shortcuts. Ctrl+J is the user-facing cross-platform newline shortcut for this
  change.
