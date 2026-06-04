## 1. Prior Completed Work

- [x] 1.1 Add line-ending-tolerant edit matching for CRLF files when model-provided `old_string` uses LF.
- [x] 1.2 Add regression tests for CRLF full-file edits, snippet-scoped CRLF edits, GBK-compatible CRLF edits, and absent-text closest-match behavior.
- [x] 1.3 Add Ctrl+J as a Windows-only newline fallback and verify Enter still submits.

## 2. Windows Newline UI Revision

- [x] 2.1 Remove Windows-specific Shift+Enter monkeypatching for `ConsoleInputReader` and `Vt100ConsoleInputReader`.
- [x] 2.2 Keep non-Windows supported Shift+Enter ANSI escape-sequence handling intact.
- [x] 2.3 Make Windows prompt toolbar/help display Ctrl+J as the newline shortcut and stop advertising Shift+Enter on Windows.
- [x] 2.4 Update prompt input tests to cover Windows Ctrl+J UI/help, Enter submit, and retained POSIX Shift+Enter escape-sequence behavior.

## 3. Byte-Preserving Writes

- [x] 3.1 Change managed text writes to encode content explicitly and write bytes instead of using platform text-mode writes.
- [x] 3.2 Add tests proving CRLF content writes as single CRLF bytes and never as CRCRLF.
- [x] 3.3 Re-run existing encoding preservation tests for UTF-8, UTF-8 with signature, UTF-16LE, and GBK-compatible files.

## 4. Windows Unicode File Creation

- [x] 4.1 Add runtime/platform-aware encoding selection for new managed text files.
- [x] 4.2 On Windows, create new non-ASCII text files as UTF-8 with signature so Windows Notepad and common IDEs identify them correctly.
- [x] 4.3 Keep macOS/Linux new text files as plain UTF-8 unless existing file encoding metadata says otherwise.
- [x] 4.4 Add tests for Windows new non-ASCII file creation, ASCII-only file creation, and non-Windows behavior.

## 5. Modify Recovery Guidance

- [x] 5.1 Update modify/edit/write tool documentation so repeated `old_string not found` failures steer the model toward re-read plus managed full-file replacement instead of shell deletion and here-string recreation.
- [x] 5.2 Improve stale delete/recreate error metadata or wording so the model understands why `modify(content=...)` is rejected after out-of-band deletion.
- [x] 5.3 Add tests for attempting managed recreation after an out-of-band deletion of a read file.

## 6. Verification

- [x] 6.1 Run focused tests for file tools and prompt input.
- [x] 6.2 Run the full test suite.
- [x] 6.3 Run `openspec validate fix-windows-modify-crlf-and-shift-enter --type change --strict`.
- [x] 6.4 Update Windows Terminal + PowerShell 7 manual verification steps for Ctrl+J, editor-readable Unicode files, CRLF preservation, and stale delete/recreate recovery.
