## Why

Windows testing after the `0.1.9` release showed that Ctrl+J reliably inserts a newline, while Shift+Enter still does not work in Windows Terminal under PowerShell 7. The same testing also showed that `modify` can still corrupt the editing workflow on Windows: repeated edits can introduce excessive blank lines, exact matches become unstable, and falling back to shell-based file creation can produce Unicode text that looks wrong in Windows editors.

## What Changes

- Make Windows terminal UI explicitly advertise Ctrl+J as the multiline newline key.
- Remove Windows-specific Shift+Enter interception and no longer promise Shift+Enter support on Windows.
- Preserve existing non-Windows Shift+Enter escape-sequence support where terminals already emit supported sequences.
- Write managed text files through explicit byte encoding instead of platform text mode so CRLF is not translated twice on Windows.
- Make Windows-created Unicode text files open correctly in Windows Notepad and common IDEs by using a UTF-8 signature when Deepy creates a new non-ASCII text file on Windows.
- Improve managed full-file replacement guidance so the model does not delete a read file and then recreate it through shell here-strings when `modify` struggles.
- Add focused regression tests for Windows newline UI, byte-preserving writes, BOM-marked Windows Unicode file creation, and stale delete/recreate failure handling.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tools`: Tighten file modification and write requirements so managed writes preserve intended bytes, line endings, and Windows editor-readable Unicode encoding.
- `terminal-ui`: Replace Windows Shift+Enter expectations with Windows Ctrl+J newline guidance while preserving Enter submission.

## Impact

- Affected code: `src/deepy/tools/builtin.py`, `src/deepy/ui/prompt_input.py`, tool documentation, and related tests.
- Affected user workflows: model-driven `modify` on Windows files containing Unicode text, full-file cleanup after repeated edit failures, and multiline prompt input in Windows Terminal with PowerShell 7.
- No breaking changes to tool function signatures, shell execution, macOS behavior, Linux behavior, or Enter submission semantics.
- Non-goal: Deepy does not guarantee that `cat` in a GBK-configured PowerShell session will render UTF-8 text correctly; the target is correct display in Windows Notepad and common IDEs.
